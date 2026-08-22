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


def _accepted_evidence_signature(
    state: Mapping[str, Any],
) -> tuple[bool, bool, tuple[str, ...], tuple[tuple[str, ...], ...]]:
    """Return ledger presence, validity, accepted IDs, and immutable evidence content.

    Evidence IDs identify the comp set. The content signature separately captures
    immutable source facts so a price/date/source/title mutation under the same ID
    is surfaced as a lineage-quality failure rather than accepted as fresh market
    evidence. Malformed rows, blank IDs, duplicate IDs, and declared count
    mismatches fail closed instead of being silently accepted into lineage.
    """
    if "evidence_ledger" not in state or state.get("evidence_ledger") is None:
        return False, True, (), ()

    ledger = state.get("evidence_ledger")
    if not isinstance(ledger, Mapping):
        return True, False, (), ()

    accepted = ledger.get("accepted")
    if not isinstance(accepted, list):
        return True, False, (), ()

    state_total = state.get("accepted_sales_total")
    if state_total is not None:
        if isinstance(state_total, bool):
            return True, False, (), ()
        try:
            state_total = int(state_total)
        except (TypeError, ValueError):
            return True, False, (), ()
        if state_total < 0 or state_total != len(accepted):
            return True, False, (), ()

    if "accepted_total" in ledger:
        accepted_total = ledger.get("accepted_total")
        if isinstance(accepted_total, bool):
            return True, False, (), ()
        try:
            accepted_total = int(accepted_total)
        except (TypeError, ValueError):
            return True, False, (), ()
        if accepted_total < 0 or accepted_total != len(accepted):
            return True, False, (), ()

    rows: list[tuple[str, ...]] = []
    seen_ids: set[str] = set()
    for row in accepted:
        if not isinstance(row, Mapping):
            return True, False, (), ()
        evidence_id = str(row.get("evidence_id") or "").strip()
        if not evidence_id or evidence_id in seen_ids:
            return True, False, (), ()
        seen_ids.add(evidence_id)
        rows.append(
            (
                evidence_id,
                str(row.get("title") or "").strip(),
                str(row.get("price") if row.get("price") is not None else ""),
                str(row.get("currency") or "").strip().upper(),
                str(row.get("event_date") or "").strip(),
                str(row.get("source") or "").strip(),
                str(row.get("url") or "").strip(),
            )
        )

    rows.sort(key=lambda row: row[0])
    ids = tuple(row[0] for row in rows)
    return True, True, ids, tuple(rows)


def _latest_sale_date_matches_ledger(
    state: Mapping[str, Any],
    *,
    has_ledger: bool,
    ledger_valid: bool,
    comp_content: tuple[tuple[str, ...], ...],
) -> bool:
    """Return whether state chronology agrees with its accepted sold ledger.

    ``latest_sale_date`` is valuation-bearing metadata. When a trusted ledger is
    present, the field must be derivable from the accepted rows rather than being
    independently mutable. Empty accepted ledgers require an empty latest-sale
    value; non-empty ledgers require the maximum accepted ``event_date``.
    """
    if not has_ledger or not ledger_valid:
        return True

    event_dates = [row[4] for row in comp_content if row[4]]
    expected = max(event_dates) if event_dates else None
    actual = str(state.get("latest_sale_date") or "").strip() or None
    return actual == expected


def _price_changed(previous: Mapping[str, Any], current: Mapping[str, Any], field: str) -> bool:
    return previous.get(field) != current.get(field)


def build_reconstruction_delta(
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any],
) -> dict[str, Any]:
    """Return an auditable explanation of how a market state changed.

    Valuation repricing is only considered supported when an input capable of
    carrying market-price information changed: sold evidence with trustworthy
    lineage, accepted comp identity, latest-sale chronology with trustworthy
    lineage, or active-supply price/count signals. Evidence-grade/confidence
    changes, loss or corruption of comp-ledger lineage, and mutation of immutable
    comp facts remain visible in the audit trail, but cannot by themselves justify
    a price move.
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

    (
        previous_has_ledger,
        previous_ledger_valid,
        previous_comp_ids,
        previous_comp_content,
    ) = _accepted_evidence_signature(previous)
    (
        current_has_ledger,
        current_ledger_valid,
        current_comp_ids,
        current_comp_content,
    ) = _accepted_evidence_signature(current)

    previous_latest_sale_valid = _latest_sale_date_matches_ledger(
        previous,
        has_ledger=previous_has_ledger,
        ledger_valid=previous_ledger_valid,
        comp_content=previous_comp_content,
    )
    current_latest_sale_valid = _latest_sale_date_matches_ledger(
        current,
        has_ledger=current_has_ledger,
        ledger_valid=current_ledger_valid,
        comp_content=current_comp_content,
    )

    sold_lineage_failure = False
    if not previous_has_ledger and not current_has_ledger:
        sold_lineage_failure = True
    elif previous_has_ledger != current_has_ledger:
        sold_lineage_failure = True
        quality_reasons.append("accepted_comp_ledger_presence_changed")
    elif previous_has_ledger and (not previous_ledger_valid or not current_ledger_valid):
        sold_lineage_failure = True
        quality_reasons.append("accepted_comp_ledger_invalid")
    elif previous_has_ledger and (not previous_latest_sale_valid or not current_latest_sale_valid):
        sold_lineage_failure = True
        quality_reasons.append("latest_sale_date_ledger_mismatch")
    elif previous_has_ledger and previous_comp_ids != current_comp_ids:
        valuation_reasons.append("accepted_comp_set_changed")
    elif previous_has_ledger and previous_comp_content != current_comp_content:
        sold_lineage_failure = True
        quality_reasons.append("accepted_comp_content_changed")

    if previous_sales != current_sales:
        if sold_lineage_failure:
            quality_reasons.append("accepted_sales_changed_without_trusted_lineage")
        else:
            valuation_reasons.append("accepted_sales_changed")

    if previous.get("latest_sale_date") != current.get("latest_sale_date"):
        if sold_lineage_failure:
            quality_reasons.append("latest_sale_changed_without_trusted_lineage")
        else:
            valuation_reasons.append("latest_sale_changed")

    previous_active = int(previous.get("accepted_active_count") or 0)
    current_active = int(current.get("accepted_active_count") or 0)
    if previous_active != current_active:
        valuation_reasons.append("active_supply_changed")

    if _price_changed(previous, current, "lowest_ask"):
        valuation_reasons.append("lowest_ask_changed")
    if _price_changed(previous, current, "median_ask"):
        valuation_reasons.append("median_ask_changed")

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


def build_reconstruction_record(
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a stable, lineage-bearing record suitable for persistence.

    The record captures which two immutable scan snapshots were compared so a
    stored delta can be audited later without relying on whichever snapshot is
    currently considered "latest". Missing or inconsistent lineage fails
    closed instead of creating an ambiguous historical record.
    """
    card_id = str(current.get("card_id") or "").strip()
    run_id = str(current.get("run_id") or "").strip()
    as_of = str(current.get("last_updated") or "").strip()
    if not card_id or not run_id or not as_of:
        raise ValueError("current state requires card_id, run_id, and last_updated")

    previous_run_id: str | None = None
    previous_as_of: str | None = None
    if previous is not None:
        previous_card_id = str(previous.get("card_id") or "").strip()
        previous_run_id = str(previous.get("run_id") or "").strip()
        previous_as_of = str(previous.get("last_updated") or "").strip()
        if not previous_card_id or not previous_run_id or not previous_as_of:
            raise ValueError("previous state requires card_id, run_id, and last_updated")
        if previous_card_id != card_id:
            raise ValueError("reconstruction states must belong to the same card")
        if previous_run_id == run_id:
            raise ValueError("reconstruction states must belong to different runs")
        if previous_as_of >= as_of:
            raise ValueError("previous state must be strictly earlier than current state")

    delta = build_reconstruction_delta(previous, current)
    lineage_key = previous_run_id or "initial"
    return {
        "schema": "market-reconstruction.v1",
        "record_id": f"{card_id}:{lineage_key}->{run_id}",
        "card_id": card_id,
        "run_id": run_id,
        "as_of": as_of,
        "previous_run_id": previous_run_id,
        "previous_as_of": previous_as_of,
        "delta": delta,
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
