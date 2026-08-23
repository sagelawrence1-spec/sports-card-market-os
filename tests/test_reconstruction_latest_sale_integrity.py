from reconstruction import build_reconstruction_delta


def _sale(evidence_id: str, event_date: str) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "title": "2024 Topps Chrome Shohei Ohtani #1 PSA 10",
        "price": 100.0,
        "currency": "USD",
        "event_date": event_date,
        "source": "ebay_product_research",
        "url": f"https://www.ebay.com/itm/{evidence_id}",
    }


def _state(*, fair_value: float, latest_sale_date: str | None, accepted: list[dict[str, object]]) -> dict[str, object]:
    return {
        "fair_value": fair_value,
        "accepted_sales_total": len(accepted),
        "latest_sale_date": latest_sale_date,
        "accepted_active_count": 0,
        "lowest_ask": None,
        "median_ask": None,
        "confidence": 0.8,
        "evidence_grade": "A",
        "evidence_ledger": {
            "accepted_total": len(accepted),
            "accepted": accepted,
        },
    }


def test_latest_sale_date_rewrite_without_ledger_change_fails_closed() -> None:
    accepted = [_sale("123456789012", "2026-08-20")]
    previous = _state(fair_value=100.0, latest_sale_date="2026-08-20", accepted=accepted)
    current = _state(fair_value=120.0, latest_sale_date="2026-08-22", accepted=accepted)

    delta = build_reconstruction_delta(previous, current)

    assert "latest_sale_date_ledger_mismatch" in delta["quality_change_reasons"]
    assert "latest_sale_changed_without_trusted_lineage" in delta["quality_change_reasons"]
    assert "latest_sale_changed" not in delta["valuation_change_reasons"]
    assert delta["valuation_input_change"] is False
    assert delta["reconstruction_health_failure"] is True


def test_latest_sale_date_tracks_newest_accepted_event() -> None:
    previous_sales = [_sale("123456789012", "2026-08-20")]
    current_sales = previous_sales + [_sale("123456789013", "2026-08-22")]
    previous = _state(fair_value=100.0, latest_sale_date="2026-08-20", accepted=previous_sales)
    current = _state(fair_value=120.0, latest_sale_date="2026-08-22", accepted=current_sales)

    delta = build_reconstruction_delta(previous, current)

    assert "latest_sale_date_ledger_mismatch" not in delta["quality_change_reasons"]
    assert "accepted_comp_set_changed" in delta["valuation_change_reasons"]
    assert "accepted_sales_changed" in delta["valuation_change_reasons"]
    assert "latest_sale_changed" in delta["valuation_change_reasons"]
    assert delta["valuation_input_change"] is True
    assert delta["reconstruction_health_failure"] is False


def test_empty_accepted_ledger_requires_empty_latest_sale_date() -> None:
    previous = _state(fair_value=100.0, latest_sale_date=None, accepted=[])
    current = _state(fair_value=120.0, latest_sale_date="2026-08-22", accepted=[])

    delta = build_reconstruction_delta(previous, current)

    assert "latest_sale_date_ledger_mismatch" in delta["quality_change_reasons"]
    assert delta["valuation_input_change"] is False
    assert delta["reconstruction_health_failure"] is True


def test_malformed_accepted_event_date_fails_closed_even_when_state_matches() -> None:
    previous_sales = [_sale("123456789012", "2026-08-20")]
    current_sales = [_sale("123456789013", "not-a-date")]
    previous = _state(fair_value=100.0, latest_sale_date="2026-08-20", accepted=previous_sales)
    current = _state(fair_value=120.0, latest_sale_date="not-a-date", accepted=current_sales)

    delta = build_reconstruction_delta(previous, current)

    assert "accepted_comp_ledger_invalid" in delta["quality_change_reasons"]
    assert "accepted_comp_set_changed" not in delta["valuation_change_reasons"]
    assert "latest_sale_changed" not in delta["valuation_change_reasons"]
    assert delta["valuation_input_change"] is False
    assert delta["reconstruction_health_failure"] is True


def test_missing_accepted_event_date_fails_closed() -> None:
    previous_sales = [_sale("123456789012", "2026-08-20")]
    current_sale = _sale("123456789013", "2026-08-22")
    current_sale.pop("event_date")
    previous = _state(fair_value=100.0, latest_sale_date="2026-08-20", accepted=previous_sales)
    current = _state(fair_value=120.0, latest_sale_date=None, accepted=[current_sale])

    delta = build_reconstruction_delta(previous, current)

    assert "accepted_comp_ledger_invalid" in delta["quality_change_reasons"]
    assert "accepted_comp_set_changed" not in delta["valuation_change_reasons"]
    assert delta["valuation_input_change"] is False
    assert delta["reconstruction_health_failure"] is True
