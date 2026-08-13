"""Compact public market history and plain-language daily change detection."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


GRADE_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "F": 4}
HISTORY_SCHEMA = "market-history.v1"
HISTORY_LIMIT = 365
SNAPSHOT_FIELDS = (
    "card_id",
    "player",
    "card",
    "sport",
    "fair_value",
    "evidence_grade",
    "confidence",
    "accepted_sales_total",
    "valuation_sample_size",
    "review_count",
    "excluded_count",
    "latest_sale_date",
    "scanned_this_run",
    "scan_state",
    "action",
)


def _count(item: Mapping[str, Any], field: str) -> int:
    try:
        return int(item.get(field) or 0)
    except (TypeError, ValueError):
        return 0


def _money(item: Mapping[str, Any], field: str) -> float | None:
    value = item.get(field)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def compact_snapshot(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Return a bounded, license-safe snapshot without raw listing rows."""
    return {
        "generated_at": contract.get("generated_at"),
        "source_kind": (contract.get("source") or {}).get("kind"),
        "items": [
            {field: deepcopy(item.get(field)) for field in SNAPSHOT_FIELDS}
            for item in contract.get("items", [])
        ],
    }


def append_history(
    history: Mapping[str, Any] | None,
    current: Mapping[str, Any],
    *,
    previous: Mapping[str, Any] | None = None,
    limit: int = HISTORY_LIMIT,
) -> dict[str, Any]:
    """Append snapshots idempotently and retain the most recent bounded window."""
    snapshots = list((history or {}).get("snapshots") or [])
    for contract in (previous, current):
        if contract and contract.get("generated_at"):
            snapshots.append(compact_snapshot(contract))
    unique = {
        snapshot.get("generated_at"): snapshot
        for snapshot in snapshots
        if snapshot.get("generated_at")
    }
    ordered = sorted(unique.values(), key=lambda snapshot: snapshot["generated_at"])
    return {
        "schema_version": HISTORY_SCHEMA,
        "updated_at": current.get("generated_at"),
        "snapshots": ordered[-max(1, int(limit)):],
    }


def build_daily_brief(
    current: dict[str, Any],
    previous: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Annotate a market contract with material, fail-closed daily changes."""
    current_items = current.get("items") or []
    review_queue = sum(_count(item, "review_count") for item in current_items)
    if not previous or not previous.get("generated_at"):
        brief = {
            "status": "collecting",
            "previous_generated_at": None,
            "summary": {
                "meaningful_changes": 0,
                "new_reliable_valuations": 0,
                "material_valuation_changes": 0,
                "weakened_markets": 0,
                "new_reviews": 0,
                "review_queue": review_queue,
            },
            "changes": [],
        }
        current["daily_brief"] = brief
        return brief

    previous_items = {
        item.get("card_id"): item
        for item in previous.get("items", [])
        if item.get("card_id")
    }
    changes = []
    for item in current_items:
        card_id = item.get("card_id")
        prior = previous_items.get(card_id)
        if prior is None:
            changes.append({
                "card_id": card_id,
                "player": item.get("player"),
                "card": item.get("card"),
                "kind": "coverage",
                "headline": "New card entered monitoring",
                "detail": "A first evidence baseline is now recorded for this card.",
                "accepted_sales_delta": _count(item, "accepted_sales_total"),
                "valuation_sample_delta": _count(item, "valuation_sample_size"),
                "review_delta": _count(item, "review_count"),
                "fair_value_delta": None,
                "fair_value_delta_pct": None,
                "evidence_grade_from": None,
                "evidence_grade_to": item.get("evidence_grade"),
                "priority": 5,
            })
            continue

        accepted_delta = _count(item, "accepted_sales_total") - _count(prior, "accepted_sales_total")
        sample_delta = _count(item, "valuation_sample_size") - _count(prior, "valuation_sample_size")
        review_delta = _count(item, "review_count") - _count(prior, "review_count")
        current_value = _money(item, "fair_value")
        prior_value = _money(prior, "fair_value")
        value_delta = None if current_value is None or prior_value is None else round(current_value - prior_value, 2)
        value_delta_pct = (
            None if value_delta is None or prior_value == 0
            else round(value_delta / prior_value * 100, 1)
        )
        current_grade = str(item.get("evidence_grade") or "F")
        prior_grade = str(prior.get("evidence_grade") or "F")
        grade_delta = GRADE_ORDER.get(current_grade, 4) - GRADE_ORDER.get(prior_grade, 4)

        kind = headline = detail = None
        priority = 99
        if prior_value is None and current_value is not None:
            kind, priority = "reliable", 1
            headline = "Valuation became publishable"
            detail = "The accepted evidence now clears the fair-value display gate."
        elif prior_value is not None and current_value is None:
            kind, priority = "weakened", 1
            headline = "Valuation was withdrawn"
            detail = "Current evidence no longer supports publishing a fair value."
        elif grade_delta > 0:
            kind, priority = "weakened", 2
            headline = f"Evidence weakened from {prior_grade} to {current_grade}"
            detail = "Recency, depth, or agreement deteriorated enough to lower the evidence grade."
        elif value_delta_pct is not None and abs(value_delta_pct) >= 5:
            kind, priority = "valuation", 2
            direction = "rose" if value_delta_pct > 0 else "fell"
            headline = f"Fair value {direction} {abs(value_delta_pct):.1f}%"
            detail = "The move is based on accepted sold evidence and cleared valuation gates."
        elif grade_delta < 0:
            kind, priority = "evidence", 3
            headline = f"Evidence improved from {prior_grade} to {current_grade}"
            detail = "The card gained enough depth, recency, or agreement to improve its grade."
        elif review_delta > 0:
            kind, priority = "review", 3
            headline = f"{review_delta} new match{'es' if review_delta != 1 else ''} held for review"
            detail = "These listings remain outside the valuation until their identity is resolved."
        elif accepted_delta != 0 or sample_delta != 0:
            kind, priority = "evidence", 4
            if accepted_delta > 0:
                headline = f"{accepted_delta} verified sale{'s' if accepted_delta != 1 else ''} added"
            elif accepted_delta < 0:
                headline = f"{abs(accepted_delta)} older sale{'s' if accepted_delta != -1 else ''} left the evidence window"
            else:
                headline = "Valuation sample changed"
            detail = f"The usable valuation sample changed by {sample_delta:+d}."
        elif item.get("scan_state") != prior.get("scan_state"):
            kind, priority = "coverage", 5
            headline = "Scan coverage changed"
            detail = "The source rotation changed whether this card was refreshed in the latest run."

        if kind:
            changes.append({
                "card_id": card_id,
                "player": item.get("player"),
                "card": item.get("card"),
                "kind": kind,
                "headline": headline,
                "detail": detail,
                "accepted_sales_delta": accepted_delta,
                "valuation_sample_delta": sample_delta,
                "review_delta": review_delta,
                "fair_value_delta": value_delta,
                "fair_value_delta_pct": value_delta_pct,
                "evidence_grade_from": prior_grade,
                "evidence_grade_to": current_grade,
                "priority": priority,
            })

    changes.sort(key=lambda change: (
        change["priority"],
        -abs(change.get("review_delta") or 0),
        str(change.get("player") or ""),
    ))
    for change in changes:
        change.pop("priority", None)

    brief = {
        "status": "ready",
        "previous_generated_at": previous.get("generated_at"),
        "summary": {
            "meaningful_changes": len(changes),
            "new_reliable_valuations": sum(change["kind"] == "reliable" for change in changes),
            "material_valuation_changes": sum(change["kind"] == "valuation" for change in changes),
            "weakened_markets": sum(change["kind"] == "weakened" for change in changes),
            "new_reviews": sum(max(0, change.get("review_delta") or 0) for change in changes),
            "review_queue": review_queue,
        },
        "changes": changes,
    }
    current["daily_brief"] = brief
    return brief
