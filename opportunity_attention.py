"""Build a compact review queue from Opportunity Radar scan deltas.

This module is read-only: it never changes engine decisions. It turns an evaluated
scan plus its movement artifact into a concise product-facing brief containing only
candidates that require attention now.
"""
from __future__ import annotations

from typing import Any, Mapping

_SCAN_SCHEMA = "opportunity-radar-scan.v1"
_DELTA_SCHEMA = "opportunity-radar-delta.v1"
_BRIEF_SCHEMA = "opportunity-radar-attention.v1"


def _index_current_candidates(scan: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    if scan.get("schema") != _SCAN_SCHEMA:
        raise ValueError(f"unsupported scan schema: {scan.get('schema')}")
    rows = scan.get("candidates")
    if not isinstance(rows, list):
        raise ValueError("scan candidates must be a list")
    out: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("scan candidate must be an object")
        player_id = row.get("player_id")
        if not isinstance(player_id, str) or not player_id.strip():
            raise ValueError("scan candidate missing player_id")
        if player_id in out:
            raise ValueError(f"duplicate player_id in scan: {player_id}")
        out[player_id] = row
    return out


def build_attention_brief(scan: Mapping[str, Any], delta: Mapping[str, Any]) -> dict[str, Any]:
    """Return only Radar movements that merit immediate human review."""
    if delta.get("schema") != _DELTA_SCHEMA:
        raise ValueError(f"unsupported delta schema: {delta.get('schema')}")
    if delta.get("current_generated_at") != scan.get("generated_at"):
        raise ValueError("delta current_generated_at must match scan generated_at")

    current = _index_current_candidates(scan)
    movements = delta.get("movements")
    if not isinstance(movements, list):
        raise ValueError("delta movements must be a list")

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for movement in movements:
        if not isinstance(movement, Mapping):
            raise ValueError("delta movement must be an object")
        player_id = movement.get("player_id")
        if not isinstance(player_id, str) or not player_id.strip():
            raise ValueError("delta movement missing player_id")
        if player_id in seen:
            raise ValueError(f"duplicate player_id in delta: {player_id}")
        seen.add(player_id)
        if not bool(movement.get("needs_attention")):
            continue

        candidate = current.get(player_id)
        changes = movement.get("changes")
        if not isinstance(changes, list) or not changes:
            raise ValueError(f"delta movement missing changes for {player_id}")

        if candidate is None:
            if "DROPPED" not in changes:
                raise ValueError(f"attention movement missing current candidate: {player_id}")
            items.append(
                {
                    "player_id": player_id,
                    "player": movement.get("player"),
                    "status": "DROPPED",
                    "changes": list(changes),
                    "became_actionable": False,
                    "current_rank": None,
                    "stage": None,
                    "decision": None,
                    "blocking_reason": None,
                    "observed_at": None,
                    "headline": None,
                    "why_now": None,
                    "thesis": None,
                    "falsification": [],
                    "source_urls": [],
                    "cards": [],
                }
            )
            continue

        items.append(
            {
                "player_id": player_id,
                "player": candidate.get("player"),
                "status": "ACTIVE",
                "changes": list(changes),
                "became_actionable": bool(movement.get("became_actionable")),
                "current_rank": candidate.get("rank"),
                "stage": candidate.get("stage"),
                "decision": candidate.get("decision"),
                "blocking_reason": candidate.get("blocking_reason"),
                "observed_at": candidate.get("observed_at"),
                "headline": candidate.get("headline"),
                "why_now": candidate.get("why_now"),
                "thesis": candidate.get("thesis"),
                "falsification": list(candidate.get("falsification") or []),
                "source_urls": list(candidate.get("source_urls") or []),
                "cards": list(candidate.get("cards") or []),
            }
        )

    items.sort(
        key=lambda row: (
            not row["became_actionable"],
            row["current_rank"] if isinstance(row["current_rank"], int) else 10**9,
            row["player_id"],
        )
    )
    return {
        "schema": _BRIEF_SCHEMA,
        "generated_at": scan["generated_at"],
        "previous_generated_at": delta.get("previous_generated_at"),
        "summary": {
            "attention_count": len(items),
            "became_actionable_count": sum(item["became_actionable"] for item in items),
            "dropped_count": sum(item["status"] == "DROPPED" for item in items),
            "waiting_for_comps_count": sum(item["decision"] == "WATCH_FOR_COMPS" for item in items),
        },
        "items": items,
    }
