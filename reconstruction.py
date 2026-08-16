"""Explain and gate scan-to-scan market-state changes."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


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

    Valuation repricing is only considered supported when an input capable of
    carrying market-price information changed: sold evidence, latest-sale
    chronology, or active supply. Evidence-grade/confidence changes remain
    visible in the audit trail, but they cannot by themselves justify a price
    move because doing so would let model metadata explain its own repricing.
    """
    if previous is None:
        return {
            "has_previous": False,
            "fair_value_change_pct": None,
            "material_input_change": True,
            "valuation_input_change": True,
            "valuation_change_reasons": ["initial_observation"],
            "quality_change_reasons": [],
            "change_reasons": ["initial_observation"],
            "unexplained_repricing": False,
            "reconstruction_health_failure": False,
        }

    valuation_reasons: list[str] = []
    quality_reasons: list[str] = []

    previous_sales = int(previous.get("accepted_sales_total") or 0)
    current_sales = int(current.get("accepted_sales_total") or 0)
    if previous_sales != current_sales:
        valuation_reasons.append("accepted_sales_changed")

    if previous.get("latest_sale_date") != current.get("latest_sale_date"):
        valuation_reasons.append("latest_sale_changed")

    previous_active = int(previous.get("accepted_active_count") or 0)
    current_active = int(current.get("accepted_active_count") or 0)
    if previous_active != current_active:
        valuation_reasons.append("active_supply_changed")

    if previous.get("evidence_grade") != current.get("evidence_grade"):
        quality_reasons.append("evidence_grade_changed")

    previous_conf = float(previous.get("confidence") or 0.0)
    current_conf = float(current.get("confidence") or 0.0)
    confidence_delta = current_conf - previous_conf
    if abs(confidence_delta) >= CONFIDENCE_CHANGE_THRESHOLD:
        quality_reasons.append("confidence_changed")

    reasons = valuation_reasons + quality_reasons
    fair_value_change = _pct_change(previous.get("fair_value"), current.get("fair_value"))
    material_input_change = bool(reasons)
    valuation_input_change = bool(valuation_reasons)
    unsupported_move = (
        fair_value_change is not None
        and abs(fair_value_change) >= UNEXPLAINED_MOVE_THRESHOLD
        and not valuation_input_change
    )
    hard_failure = (
        fair_value_change is not None
        and abs(fair_value_change) >= HARD_FAILURE_THRESHOLD
        and not valuation_input_change
    )

    return {
        "has_previous": True,
        "previous_as_of": previous.get("last_updated"),
        "fair_value_change_pct": fair_value_change,
        "accepted_sales_delta": current_sales - previous_sales,
        "active_supply_delta": current_active - previous_active,
        "confidence_delta": confidence_delta,
        "material_input_change": material_input_change,
        "valuation_input_change": valuation_input_change,
        "valuation_change_reasons": valuation_reasons,
        "quality_change_reasons": quality_reasons,
        "change_reasons": reasons or ["no_material_input_change"],
        "unexplained_repricing": unsupported_move,
        "reconstruction_health_failure": hard_failure,
    }


def summarize_reconstruction_health(states: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize reconstruction integrity across the current card universe.

    The input should contain the latest persisted state for each card. The summary
    is deliberately fail-closed: any hard reconstruction failure makes universe
    health ``failed``; non-hard unexplained repricing degrades health and surfaces
    the affected cards for review.
    """
    rows = list(states)
    total_cards = len(rows)
    with_previous = 0
    unexplained_cards: list[str] = []
    hard_failure_cards: list[str] = []

    for state in rows:
        card_id = str(state.get("card_id") or "").strip() or "unknown"
        reconstruction = state.get("reconstruction") or {}
        if reconstruction.get("has_previous"):
            with_previous += 1
        if reconstruction.get("unexplained_repricing"):
            unexplained_cards.append(card_id)
        if reconstruction.get("reconstruction_health_failure"):
            hard_failure_cards.append(card_id)

    unexplained_cards = sorted(set(unexplained_cards))
    hard_failure_cards = sorted(set(hard_failure_cards))
    review_cards = sorted(set(unexplained_cards) | set(hard_failure_cards))

    if hard_failure_cards:
        status = "failed"
    elif unexplained_cards:
        status = "degraded"
    else:
        status = "healthy"

    denominator = with_previous or 1
    return {
        "status": status,
        "total_cards": total_cards,
        "cards_with_previous": with_previous,
        "initial_observations": total_cards - with_previous,
        "unexplained_repricing_count": len(unexplained_cards),
        "hard_failure_count": len(hard_failure_cards),
        "unexplained_repricing_rate": len(unexplained_cards) / denominator,
        "hard_failure_rate": len(hard_failure_cards) / denominator,
        "cards_requiring_review": review_cards,
        "hard_failure_cards": hard_failure_cards,
    }
