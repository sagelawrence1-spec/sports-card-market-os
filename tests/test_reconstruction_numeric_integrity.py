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


def _state(*, fair_value: float, accepted_sales_total: object, accepted: list[dict[str, object]]) -> dict[str, object]:
    return {
        "fair_value": fair_value,
        "accepted_sales_total": accepted_sales_total,
        "latest_sale_date": max((row["event_date"] for row in accepted), default=None),
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


def test_malformed_accepted_sales_total_fails_closed_instead_of_crashing() -> None:
    accepted = [_sale("123456789012", "2026-08-20")]
    previous = _state(fair_value=100.0, accepted_sales_total=1, accepted=accepted)
    current = _state(fair_value=120.0, accepted_sales_total="not-a-number", accepted=accepted)

    delta = build_reconstruction_delta(previous, current)

    assert "accepted_sales_total_invalid" in delta["quality_change_reasons"]
    assert delta["valuation_input_change"] is False
    assert delta["reconstruction_health_failure"] is True


def test_negative_accepted_sales_total_cannot_legitimize_comp_set_change() -> None:
    previous_sales = [_sale("123456789012", "2026-08-20")]
    current_sales = [_sale("123456789013", "2026-08-22")]
    previous = _state(fair_value=100.0, accepted_sales_total=1, accepted=previous_sales)
    current = _state(fair_value=120.0, accepted_sales_total=-1, accepted=current_sales)

    delta = build_reconstruction_delta(previous, current)

    assert "accepted_sales_total_invalid" in delta["quality_change_reasons"]
    assert "accepted_comp_set_changed" not in delta["valuation_change_reasons"]
    assert delta["valuation_input_change"] is False
    assert delta["reconstruction_health_failure"] is True
