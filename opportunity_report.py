"""Serializable product artifact for Opportunity Radar batch scans.

The report is intentionally read-only: it converts an evaluated RadarBatchReport into
stable JSON-ready data for review, persistence, and later outcome grading without
changing any thesis or action decision.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from statistics import median
from typing import Any

from opportunity_radar import RadarBatchReport


_SOURCE_QUALITIES = {"OFFICIAL", "CORROBORATED", "SINGLE_SOURCE"}


def _aware_utc(value: str, *, field: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _utc_iso(value: str | None = None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    return _aware_utc(value, field="generated_at").isoformat()


def build_radar_scan_artifact(report: RadarBatchReport, *, generated_at: str | None = None) -> dict[str, Any]:
    """Return a deterministic JSON-ready scan artifact from an evaluated Radar batch."""
    if report.schema != "opportunity-radar-batch.v1":
        raise ValueError(f"unsupported Radar batch schema: {report.schema}")

    generated_at_utc = _utc_iso(generated_at)
    generated_at_dt = _aware_utc(generated_at_utc, field="generated_at")
    observation_lags: list[float] = []
    candidates: list[dict[str, Any]] = []
    for rank, candidate in enumerate(report.candidates, start=1):
        if candidate.source_quality not in _SOURCE_QUALITIES:
            raise ValueError(f"unsupported source quality: {candidate.source_quality}")
        if not isinstance(candidate.source_host_count, int) or isinstance(candidate.source_host_count, bool) or candidate.source_host_count < 1:
            raise ValueError("source_host_count must be a positive integer")

        thesis = candidate.thesis
        observed_at = thesis.signals[-1].observed_at if thesis.signals else None
        observation_to_scan_lag_minutes: float | None = None
        if observed_at is not None:
            observed_at_dt = _aware_utc(observed_at, field="observed_at")
            if observed_at_dt > generated_at_dt:
                raise ValueError("candidate observed_at cannot be after generated_at")
            observation_to_scan_lag_minutes = round(
                (generated_at_dt - observed_at_dt).total_seconds() / 60.0,
                2,
            )
            observation_lags.append(observation_to_scan_lag_minutes)

        candidates.append(
            {
                "rank": rank,
                "thesis_id": thesis.thesis_id,
                "player_id": thesis.player_id,
                "player": thesis.player,
                "sport": thesis.sport,
                "thesis_type": thesis.thesis_type.value,
                "stage": thesis.stage.value,
                "decision": candidate.decision,
                "blocking_reason": candidate.blocking_reason,
                "market_price_verified": candidate.market_price_verified,
                "observed_at": observed_at,
                "observation_to_scan_lag_minutes": observation_to_scan_lag_minutes,
                "headline": thesis.headline,
                "why_now": thesis.why_now,
                "thesis": thesis.thesis,
                "falsification": list(thesis.falsification),
                "edge_conviction": thesis.edge_conviction,
                "evidence_confidence": thesis.evidence_confidence,
                "asymmetry": thesis.asymmetry,
                "source_urls": list(candidate.source_urls),
                "source_quality": candidate.source_quality,
                "source_host_count": candidate.source_host_count,
                "cards": [
                    {
                        "card_id": card.card_id,
                        "label": card.label,
                        "priority": card.priority,
                        "current_price": card.current_price,
                        "buy_below": card.buy_below,
                        "avoid_above": card.avoid_above,
                        "rationale": card.rationale,
                    }
                    for card in thesis.cards
                ],
            }
        )

    return {
        "schema": "opportunity-radar-scan.v1",
        "generated_at": generated_at_utc,
        "source_schema": report.schema,
        "summary": {
            "input_count": report.input_count,
            "candidate_count": report.candidate_count,
            "actionable_count": report.actionable_count,
            "duplicate_count": report.duplicate_count,
            "failure_count": len(report.failures),
            "waiting_for_comps_count": sum(c.decision == "WATCH_FOR_COMPS" for c in report.candidates),
            "official_source_count": sum(c.source_quality == "OFFICIAL" for c in report.candidates),
            "corroborated_source_count": sum(c.source_quality == "CORROBORATED" for c in report.candidates),
            "single_source_count": sum(c.source_quality == "SINGLE_SOURCE" for c in report.candidates),
            "observed_at_count": len(observation_lags),
            "missing_observed_at_count": report.candidate_count - len(observation_lags),
            "median_observation_to_scan_lag_minutes": round(median(observation_lags), 2) if observation_lags else None,
            "max_observation_to_scan_lag_minutes": max(observation_lags) if observation_lags else None,
        },
        "candidates": candidates,
        "failures": [asdict(failure) for failure in report.failures],
    }
