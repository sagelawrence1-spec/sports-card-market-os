from reconstruction import build_reconstruction_delta


def _row(evidence_id: str, price: float = 100.0):
    return {
        "evidence_id": evidence_id,
        "title": f"Card {evidence_id}",
        "price": price,
        "currency": "USD",
        "event_date": "2026-08-11",
        "source": "eBay Product Research",
        "url": f"https://www.ebay.com/itm/{evidence_id[-1]}1234567890",
    }


def _state(*, fair_value=100.0, accepted_sales_total=2, accepted=None, ledger_total=None):
    accepted = accepted if accepted is not None else [_row("sale-1"), _row("sale-2", 102.0)]
    ledger = {"accepted": accepted}
    if ledger_total is not None:
        ledger["accepted_total"] = ledger_total
    return {
        "card_id": "card-1",
        "run_id": "run-2",
        "last_updated": "2026-08-12T12:00:00Z",
        "fair_value": fair_value,
        "accepted_sales_total": accepted_sales_total,
        "latest_sale_date": "2026-08-11",
        "accepted_active_count": 2,
        "lowest_ask": 120.0,
        "median_ask": 130.0,
        "evidence_grade": "A",
        "confidence": 0.8,
        "evidence_ledger": ledger,
    }


def test_ledger_total_must_match_accepted_rows_before_repricing_is_trusted():
    delta = build_reconstruction_delta(
        _state(ledger_total=2),
        _state(fair_value=116.0, accepted_sales_total=3, ledger_total=3),
    )

    assert delta["valuation_change_reasons"] == []
    assert delta["quality_change_reasons"] == [
        "accepted_comp_ledger_invalid",
        "accepted_sales_changed_without_trusted_lineage",
    ]
    assert delta["valuation_input_change"] is False
    assert delta["unexplained_repricing"] is True
    assert delta["reconstruction_health_failure"] is True


def test_state_sale_total_must_match_ledger_total():
    delta = build_reconstruction_delta(
        _state(ledger_total=2),
        _state(fair_value=116.0, accepted_sales_total=3, ledger_total=2),
    )

    assert delta["valuation_change_reasons"] == []
    assert delta["quality_change_reasons"] == [
        "accepted_comp_ledger_invalid",
        "accepted_sales_changed_without_trusted_lineage",
    ]
    assert delta["reconstruction_health_failure"] is True


def test_consistent_ledger_count_preserves_real_comp_set_change():
    previous = _state(accepted_sales_total=2, ledger_total=2)
    current_rows = [_row("sale-1"), _row("sale-2", 102.0), _row("sale-3", 103.0)]
    current = _state(
        fair_value=108.0,
        accepted_sales_total=3,
        accepted=current_rows,
        ledger_total=3,
    )

    delta = build_reconstruction_delta(previous, current)

    assert delta["valuation_change_reasons"] == [
        "accepted_comp_set_changed",
        "accepted_sales_changed",
    ]
    assert delta["quality_change_reasons"] == []
    assert delta["valuation_input_change"] is True
    assert delta["unexplained_repricing"] is False
