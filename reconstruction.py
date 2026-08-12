"""Explain and gate scan-to-scan market-state changes."""

from __future__ import annotations

from typing import Any, Mapping


UNEXPLAINED_MOVE_THRESHOLD = 0.08
HARD_FAILURE_THRESHOLD = 0.15
CONFIDENCE_CHANGE_THRESHOLD = 0.05


def _pct_change(previous: float | None, current: float | None) -> float | None:
    if previous is None or current is None or previous == 0:
        return None
    return (float(current) - float(previous)) / float(previous)


def build_reconstruction_delta(
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any],
) -> dict[str, Any]:
    """Return an auditable explanation of how a market state changed.

    A valuation move is considered supported when at least one material input also
    changed: accepted sold depth, latest-sale date, active supply, evidence grade,
    or confidence. Large moves without such evidence fail closed.
    """
    if previous is None:
        return {
            "has_previous": False,
            "fair_value_change_pct": None,
            "material_input_change": True,
            "change_reasons": ["initial_observation"],
            "unexplained_repricing": False,
            "reconstruction_health_failure": False,
        }

    reasons: list[str] = []

    previous_sales = int(previous.get("accepted_sales_total") or 0)
    current_sales = int(current.get("accepted_sales_total") or 0)
    if previous_sales != current_sales:
        reasons.append("accepted_sales_changed")

    if previous.get("latest_sale_date") != current.get("latest_sale_date"):
        reasons.append("latest_sale_changed")

    previous_active = int(previous.get("accepted_active_count") or 0)
    current_active = int(current.get("accepted_active_count") or 0)
    if previous_active != current_active:
        reasons.append("active_supply_changed")

    if previous.get("evidence_grade") != current.get("evidence_grade"):
        reasons.append("evidence_grade_changed")

    previous_conf = float(previous.get("confidence") or 0.0)
    current_conf = float(current.get("confidence") or 0.0)
    confidence_delta = current_conf - previous_conf
    if abs(confidence_delta) >= CONFIDENCE_CHANGE_THRESHOLD:
        reasons.append("confidence_changed")

    fair_value_change = _pct_change(previous.get("fair_value"), current.get("fair_value"))
    material_input_change = bool(reasons)
    unsupported_move = (
        fair_value_change is not None
        and abs(fair_value_change) >= UNEXPLAINED_MOVE_THRESHOLD
        and not material_input_change
    )
    hard_failure = (
        fair_value_change is not None
        and abs(fair_value_change) >= HARD_FAILURE_THRESHOLD
        and not material_input_change
    )

    return {
        "has_previous": True,
        "previous_as_of": previous.get("last_updated"),
        "fair_value_change_pct": fair_value_change,
        "accepted_sales_delta": current_sales - previous_sales,
        "active_supply_delta": current_active - previous_active,
        "confidence_delta": confidence_delta,
        "material_input_change": material_input_change,
        "change_reasons": reasons or ["no_material_input_change"],
        "unexplained_repricing": unsupported_move,
        "reconstruction_health_failure": hard_failure,
    }
