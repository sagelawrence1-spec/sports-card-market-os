"""Compare Opportunity Radar scan artifacts without mutating engine decisions.

This module turns two `opportunity-radar-scan.v1` artifacts into a stable,
reviewable movement feed keyed by durable player identity. Thesis UUIDs may change
between independent scans, so they are preserved as evidence rather than used as
the join key.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping


_SCAN_SCHEMA = "opportunity-radar-scan.v1"
_DELTA_SCHEMA = "opportunity-radar-delta.v1"
_ACTIONABLE = {"START_POSITION", "ADD"}
_STAGE_ORDER = {
    "PRE_CATALYST": 0,
    "ENTRY": 1,
    "ACCELERATION": 2,
    "CONSENSUS": 3,
    "BROKEN": 99,
}


def _parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a timezone-aware ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a timezone-aware ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed


def _candidate_index(scan: Mapping[str, Any], *, label: str) -> dict[str, Mapping[str, Any]]:
    if scan.get("schema") != _SCAN_SCHEMA:
        raise ValueError(f"unsupported {label} scan schema: {scan.get('schema')}")
    rows = scan.get("candidates")
    if not isinstance(rows, list):
        raise ValueError(f"{label} candidates must be a list")
    out: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError(f"{label} candidate must be an object")
        player_id = row.get("player_id")
        if not isinstance(player_id, str) or not player_id.strip():
            raise ValueError(f"{label} candidate missing player_id")
        if player_id in out:
            raise ValueError(f"duplicate player_id in {label} scan: {player_id}")
        out[player_id] = row
    return out


def _movement(previous: Mapping[str, Any] | None, current: Mapping[str, Any] | None) -> list[str]:
    if previous is None:
        return ["NEW"]
    if current is None:
        return ["DROPPED"]

    changes: list[str] = []
    old_stage = previous.get("stage")
    new_stage = current.get("stage")
    if old_stage != new_stage:
        old_order = _STAGE_ORDER.get(str(old_stage), -1)
        new_order = _STAGE_ORDER.get(str(new_stage), -1)
        changes.append("STAGE_ADVANCED" if new_order > old_order else "STAGE_CHANGED")

    if previous.get("decision") != current.get("decision"):
        changes.append("DECISION_CHANGED")
    if not bool(previous.get("market_price_verified")) and bool(current.get("market_price_verified")):
        changes.append("REPRICING_VERIFIED")
    if previous.get("blocking_reason") != current.get("blocking_reason"):
        changes.append("BLOCKER_CHANGED")
    if previous.get("rank") != current.get("rank"):
        changes.append("RANK_CHANGED")
    if previous.get("edge_conviction") != current.get("edge_conviction"):
        changes.append("EDGE_CHANGED")
    if previous.get("evidence_confidence") != current.get("evidence_confidence"):
        changes.append("EVIDENCE_CHANGED")
    return changes or ["UNCHANGED"]


def build_radar_scan_delta(previous_scan: Mapping[str, Any], current_scan: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deterministic scan-to-scan movement artifact.

    The function is read-only and deliberately does not infer a buy signal. It only
    reports how the already-evaluated Opportunity Radar output changed.
    """
    previous_at = _parse_timestamp(previous_scan.get("generated_at"), "previous generated_at")
    current_at = _parse_timestamp(current_scan.get("generated_at"), "current generated_at")
    if current_at <= previous_at:
        raise ValueError("current scan must be strictly later than previous scan")

    previous = _candidate_index(previous_scan, label="previous")
    current = _candidate_index(current_scan, label="current")
    player_ids = sorted(set(previous) | set(current))

    movements: list[dict[str, Any]] = []
    for player_id in player_ids:
        old = previous.get(player_id)
        new = current.get(player_id)
        changes = _movement(old, new)
        prior_decision = old.get("decision") if old else None
        current_decision = new.get("decision") if new else None
        became_actionable = current_decision in _ACTIONABLE and prior_decision not in _ACTIONABLE
        needs_attention = became_actionable or any(
            change in {"NEW", "DROPPED", "STAGE_ADVANCED", "DECISION_CHANGED", "REPRICING_VERIFIED", "BLOCKER_CHANGED"}
            for change in changes
        )
        source = new or old
        movements.append(
            {
                "player_id": player_id,
                "player": source.get("player"),
                "previous_thesis_id": old.get("thesis_id") if old else None,
                "current_thesis_id": new.get("thesis_id") if new else None,
                "previous_rank": old.get("rank") if old else None,
                "current_rank": new.get("rank") if new else None,
                "previous_stage": old.get("stage") if old else None,
                "current_stage": new.get("stage") if new else None,
                "previous_decision": prior_decision,
                "current_decision": current_decision,
                "market_price_verified": bool(new.get("market_price_verified")) if new else None,
                "changes": changes,
                "became_actionable": became_actionable,
                "needs_attention": needs_attention,
            }
        )

    movements.sort(
        key=lambda row: (
            not row["needs_attention"],
            not row["became_actionable"],
            row["current_rank"] if row["current_rank"] is not None else 10**9,
            row["player_id"],
        )
    )
    return {
        "schema": _DELTA_SCHEMA,
        "previous_generated_at": previous_scan["generated_at"],
        "current_generated_at": current_scan["generated_at"],
        "summary": {
            "tracked_count": len(movements),
            "new_count": sum("NEW" in row["changes"] for row in movements),
            "dropped_count": sum("DROPPED" in row["changes"] for row in movements),
            "changed_count": sum(row["changes"] != ["UNCHANGED"] for row in movements),
            "attention_count": sum(row["needs_attention"] for row in movements),
            "became_actionable_count": sum(row["became_actionable"] for row in movements),
        },
        "movements": movements,
    }
