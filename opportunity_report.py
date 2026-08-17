"""Serializable product artifact for Opportunity Radar batch scans.

The report is intentionally read-only: it converts an evaluated RadarBatchReport into
stable JSON-ready data for review, persistence, and later outcome grading without
changing any thesis or action decision.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from opportunity_radar import RadarBatchReport


def _utc_iso(value: str | None = None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    return parsed.astimezone(timezone.utc).isoformat()


def build_radar_scan_artifact(report: RadarBatchReport, *, generated_at: str | None = None) -> dict[str, Any]:
    """Return a deterministic JSON-ready scan artifact from an evaluated Radar batch."""
    if report.schema != "opportunity-radar-batch.v1":
        raise ValueError(f"unsupported Radar batch schema: {report.schema}")

    candidates: list[dict[str, Any]] = []
    for rank, candidate in enumerate(report.candidates, start=1):
        thesis = candidate.thesis
        observed_at = thesis.signals[-1].observed_at if thesis.signals else None
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
                "headline": thesis.headline,
                "why_now": thesis.why_now,
                "thesis": thesis.thesis,
                "falsification": list(thesis.falsification),
                "edge_conviction": thesis.edge_conviction,
                "evidence_confidence": thesis.evidence_confidence,
                "asymmetry": thesis.asymmetry,
                "source_urls": list(candidate.source_urls),
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
        "generated_at": _utc_iso(generated_at),
        "source_schema": report.schema,
        "summary": {
            "input_count": report.input_count,
            "candidate_count": report.candidate_count,
            "actionable_count": report.actionable_count,
            "duplicate_count": report.duplicate_count,
            "failure_count": len(report.failures),
            "waiting_for_comps_count": sum(c.decision == "WATCH_FOR_COMPS" for c in report.candidates),
        },
        "candidates": candidates,
        "failures": [asdict(failure) for failure in report.failures],
    }
