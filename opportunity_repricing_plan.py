"""Build deterministic sold-data collection windows from Opportunity Radar scans."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

AUTHORITATIVE_SOURCE = "EBAY_PRODUCT_RESEARCH"
_PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}


def _parse_time(value: str, *, field: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _collection_priority(candidate: Mapping[str, Any]) -> tuple[str, str]:
    """Prioritize scarce manual Product Research pulls without changing capital logic."""
    decision = str(candidate.get("decision", ""))
    stage = str(candidate.get("stage", ""))
    lag_raw = candidate.get("observation_to_scan_lag_minutes")
    lag_minutes = float(lag_raw) if lag_raw is not None else None

    waiting = decision == "WATCH_FOR_COMPS"
    fresh = lag_minutes is not None and lag_minutes <= 24 * 60
    earliest_stage = stage in {"PRE_CATALYST", "ENTRY"}

    if waiting and fresh and earliest_stage:
        return "P0", "fresh early-stage opportunity waiting on authoritative comps"
    if waiting and (fresh or stage == "ACCELERATION"):
        return "P1", "active opportunity waiting on authoritative comps"
    return "P2", "lower-urgency repricing verification"


def build_repricing_plan(
    scan: Mapping[str, Any],
    *,
    as_of: str | None = None,
    pre_window_days: int = 30,
    post_window_days: int = 7,
    min_pre_comps: int = 3,
    min_post_comps: int = 3,
) -> dict[str, Any]:
    """Translate a Radar scan into exact authoritative sold-comp collection requests.

    Each card expression receives a point-in-time request anchored to the catalyst's
    actual ``observed_at`` timestamp, never the scan generation timestamp. Requests
    expose the full intended pre/post windows plus the currently queryable post cutoff
    so collection can run immediately without leaking future sales.

    Requests are also assigned a deterministic collection priority. This is an
    operational queue only: it decides which Product Research export should be pulled
    first and does not alter Radar scoring, repricing thresholds, or capital actions.
    """
    if scan.get("schema") != "opportunity-radar-scan.v1":
        raise ValueError("unsupported Radar scan schema")
    if pre_window_days < 1 or post_window_days < 1:
        raise ValueError("pricing windows must be positive")
    if min_pre_comps < 1 or min_post_comps < 1:
        raise ValueError("minimum comp counts must be positive")

    generated_at = _parse_time(str(scan.get("generated_at", "")), field="generated_at")
    cutoff = _parse_time(as_of, field="as_of") if as_of is not None else generated_at

    requests: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in scan.get("candidates", ()):
        player_id = str(candidate.get("player_id", "")).strip()
        if not player_id:
            raise ValueError("Radar candidate requires player_id")
        observed_raw = candidate.get("observed_at")
        if not observed_raw:
            raise ValueError(f"Radar candidate {player_id} requires observed_at")
        catalyst = _parse_time(str(observed_raw), field="observed_at")
        if cutoff < catalyst:
            raise ValueError(f"as_of cannot precede catalyst for {player_id}")

        cards = candidate.get("cards") or ()
        if not cards:
            raise ValueError(f"Radar candidate {player_id} requires at least one card expression")

        pre_start = catalyst - timedelta(days=pre_window_days)
        post_window_end = catalyst + timedelta(days=post_window_days)
        queryable_post_end = min(cutoff, post_window_end)
        status = "WINDOW_MATURE" if cutoff >= post_window_end else "COLLECTION_OPEN"
        collection_priority, collection_priority_reason = _collection_priority(candidate)

        for card in cards:
            card_id = str(card.get("card_id", "")).strip()
            if not card_id:
                raise ValueError(f"Radar candidate {player_id} has card without card_id")
            identity = (player_id, card_id)
            if identity in seen:
                raise ValueError(f"duplicate repricing request identity: {player_id}/{card_id}")
            seen.add(identity)
            requests.append(
                {
                    "player_id": player_id,
                    "player": candidate.get("player"),
                    "thesis_id": candidate.get("thesis_id"),
                    "candidate_rank": candidate.get("rank"),
                    "stage": candidate.get("stage"),
                    "decision": candidate.get("decision"),
                    "card_id": card_id,
                    "card_label": card.get("label"),
                    "card_priority": card.get("priority"),
                    "collection_priority": collection_priority,
                    "collection_priority_reason": collection_priority_reason,
                    "source_type": AUTHORITATIVE_SOURCE,
                    "catalyst_at": catalyst.isoformat(),
                    "pre_start": pre_start.isoformat(),
                    "pre_end_exclusive": catalyst.isoformat(),
                    "post_start": catalyst.isoformat(),
                    "post_window_end": post_window_end.isoformat(),
                    "queryable_post_end": queryable_post_end.isoformat(),
                    "as_of": cutoff.isoformat(),
                    "min_pre_comps": min_pre_comps,
                    "min_post_comps": min_post_comps,
                    "status": status,
                }
            )

    requests.sort(
        key=lambda row: (
            _PRIORITY_ORDER[row["collection_priority"]],
            row["candidate_rank"] if row["candidate_rank"] is not None else 999,
            row["card_priority"] or 999,
            row["player_id"],
            row["card_id"],
        )
    )
    return {
        "schema": "opportunity-repricing-plan.v1",
        "source_scan_generated_at": generated_at.isoformat(),
        "as_of": cutoff.isoformat(),
        "source_type": AUTHORITATIVE_SOURCE,
        "request_count": len(requests),
        "open_count": sum(row["status"] == "COLLECTION_OPEN" for row in requests),
        "mature_count": sum(row["status"] == "WINDOW_MATURE" for row in requests),
        "priority_counts": {
            priority: sum(row["collection_priority"] == priority for row in requests)
            for priority in ("P0", "P1", "P2")
        },
        "requests": requests,
    }
