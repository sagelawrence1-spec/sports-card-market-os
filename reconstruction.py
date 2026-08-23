"""Explain and gate scan-to-scan market-state changes."""

from __future__ import annotations

from datetime import date
from math import isfinite
from typing import Any, Iterable, Mapping


UNEXPLAINED_MOVE_THRESHOLD = 0.08
HARD_FAILURE_THRESHOLD = 0.15
CONFIDENCE_CHANGE_THRESHOLD = 0.05


def _pct_change(previous: float | None, current: float | None) -> float | None:
    if previous is None or current is None or previous == 0:
        return None
    return (float(current) - float(previous)) / float(previous)


def _nonnegative_int(value: Any) -> int | None:
    """Return a non-negative integer or ``None`` for malformed metadata."""
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _optional_nonnegative_float(value: Any) -> tuple[bool, float | None]:
    """Parse optional price metadata without trusting malformed/non-finite values."""
    if value is None or value == "":
        return True, None
    if isinstance(value, bool):
        return False, None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return False, None
    if not isfinite(parsed) or parsed < 0:
        return False, None
    return True, parsed


def _required_positive_float(value: Any) -> tuple[bool, float | None]:
    """Parse required valuation metadata as a finite, strictly positive number."""
    if isinstance(value, bool):
        return False, None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return False, None
    if not isfinite(parsed) or parsed <= 0:
        return False, None
    return True, parsed


def _confidence_value(value: Any) -> tuple[bool, float]:
    """Parse confidence as a finite probability while preserving legacy omission."""
    if value is None or value == "":
        return True, 0.0
    if isinstance(value, bool):
        return False, 0.0
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return False, 0.0
    if not isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        return False, 0.0
    return True, parsed


def _canonical_event_date(value: Any) -> str | None:
    """Return a strict ISO calendar date or ``None`` for malformed input."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        return None
    if parsed.isoformat() != text:
        return None
    return text


def _accepted_evidence_signature(
    state: Mapping[str, Any],
) -> tuple[bool, bool, tuple[str, ...], tuple[tuple[str, ...], ...]]:
    """Return ledger presence, validity, accepted IDs, and immutable evidence content.

    Evidence IDs identify the comp set. The content signature separately captures
    immutable source facts so a price/date/source/title mutation under the same ID
    is surfaced as a lineage-quality failure rather than accepted as fresh market
    evidence. Malformed rows, blank IDs, duplicate IDs, invalid sold dates, and
    declared count mismatches fail closed instead of being silently accepted into
    lineage.
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
        state_total = _nonnegative_int(state_total)
        if state_total is None or state_total != len(accepted):
            return True, False, (), ()

    if "accepted_total" in ledger:
        accepted_total = _nonnegative_int(ledger.get("accepted_total"))
        if accepted_total is None or accepted_total != len(accepted):
            return True, False, (), ()

    rows: list[tuple[str, ...]] = []
    seen_ids: set[str] = set()
    for row in accepted:
        if not isinstance(row, Mapping):
            return True, False, (), ()
        evidence_id = str(row.get("evidence_id") or "").strip()
        if not evidence_id or evidence_id in seen_ids:
            return True, False, (), ()
        event_date = _canonical_event_date(row.get("event_date"))
        if event_date is None:
            return True, False, (), ()
        seen_ids.add(evidence_id)
        rows.append(
            (
                evidence_id,
                str(row.get("title") or "").strip(),
                str(row.get("price") if row.get("price") is not None else ""),
                str(row.get("currency") or "").strip().upper(),
                event_date,
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

    event_dates = [row[4] for row in comp_content]
    expected = max(event_dates) if event_dates else None
    actual = str(state.get("latest_sale_date") or "").strip() or None
    return actual == expected


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
    current_fair_value_valid, current_fair_value = _required_positive_float(current.get("fair_value"))
    if previous is None:
        if not current_fair_value_valid:
            return {
                "has_previous": False,
                "fair_value_change_pct": None,
                "material_input_change": True,
                "valuation_input_change": False,
                "valuation_change_reasons": [],
                "quality_change_reasons": ["fair_value_invalid"],
                "change_reasons": ["fair_value_invalid"],
                "unexplained_repricing": False,
                "reconstruction_health_failure": True,
            }
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

    previous_fair_value_valid, previous_fair_value = _required_positive_float(previous.get("fair_value"))
    fair_value_invalid = not previous_fair_value_valid or not current_fair_value_valid
    if fair_value_invalid:
        quality_reasons.append("fair_value_invalid")

    previous_sales_value = _nonnegative_int(previous.get("accepted_sales_total"))
    current_sales_value = _nonnegative_int(current.get("accepted_sales_total"))
    sales_metadata_invalid = previous_sales_value is None or current_sales_value is None
    previous_sales = previous_sales_value or 0
    current_sales = current_sales_value or 0
    if sales_metadata_invalid:
        quality_reasons.append("accepted_sales_total_invalid")

    previous_active_raw = previous.get("accepted_active_count")
    current_active_raw = current.get("accepted_active_count")
    previous_active_value = 0 if previous_active_raw is None else _nonnegative_int(previous_active_raw)
    current_active_value = 0 if current_active_raw is None else _nonnegative_int(current_active_raw)
    active_metadata_invalid = previous_active_value is None or current_active_value is None
    previous_active = previous_active_value or 0
    current_active = current_active_value or 0
    if active_metadata_invalid:
        quality_reasons.append("accepted_active_count_invalid")

    previous_lowest_valid, previous_lowest = _optional_nonnegative_float(previous.get("lowest_ask"))
    current_lowest_valid, current_lowest = _optional_nonnegative_float(current.get("lowest_ask"))
    lowest_ask_invalid = not previous_lowest_valid or not current_lowest_valid
    if lowest_ask_invalid:
        quality_reasons.append("lowest_ask_invalid")

    previous_median_valid, previous_median = _optional_nonnegative_float(previous.get("median_ask"))
    current_median_valid, current_median = _optional_nonnegative_float(current.get("median_ask"))
    median_ask_invalid = not previous_median_valid or not current_median_valid
    if median_ask_invalid:
        quality_reasons.append("median_ask_invalid")

    previous_conf_valid, previous_conf = _confidence_value(previous.get("confidence"))
    current_conf_valid, current_conf = _confidence_value(current.get("confidence"))
    confidence_invalid = not previous_conf_valid or not current_conf_valid
    if confidence_invalid:
        quality_reasons.append("confidence_invalid")

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

    sold_lineage_failure = sales_metadata_invalid
    if sales_metadata_invalid:
        pass
    elif not previous_has_ledger and not current_has_ledger:
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

    if previous_active != current_active:
        if active_metadata_invalid:
            quality_reasons.append("active_supply_changed_without_trusted_metadata")
        else:
            valuation_reasons.append("active_supply_changed")

    if previous_lowest != current_lowest:
        if lowest_ask_invalid:
            quality_reasons.append("lowest_ask_changed_without_trusted_metadata")
        else:
            valuation_reasons.append("lowest_ask_changed")
    if previous_median != current_median:
        if median_ask_invalid:
            quality_reasons.append("median_ask_changed_without_trusted_metadata")
        else:
            valuation_reasons.append("median_ask_changed")

    if previous.get("evidence_grade") != current.get("evidence_grade"):
        quality_reasons.append("evidence_grade_changed")

    confidence_delta = current_conf - previous_conf
    if not confidence_invalid and abs(confidence_delta) >= CONFIDENCE_CHANGE_THRESHOLD:
        quality_reasons.append("confidence_changed")

    reasons = valuation_reasons + quality_reasons
    fair_value_change = None if fair_value_invalid else _pct_change(previous_fair_value, current_fair_value)
    material_input_change = bool(reasons)
    valuation_input_change = bool(valuation_reasons)
    unsupported_move = (
        fair_value_change is not None
        and abs(fair_value_change) >= UNEXPLAINED_MOVE_THRESHOLD
        and not valuation_input_change
    )
    hard_failure = fair_value_invalid or (
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