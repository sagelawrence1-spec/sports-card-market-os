from reconstruction import build_reconstruction_delta


def _state(*, fair_value: float, active_count: object) -> dict[str, object]:
    return {
        "fair_value": fair_value,
        "accepted_sales_total": 0,
        "latest_sale_date": None,
        "accepted_active_count": active_count,
        "lowest_ask": None,
        "median_ask": None,
        "confidence": 0.8,
        "evidence_grade": "A",
        "evidence_ledger": {
            "accepted_total": 0,
            "accepted": [],
        },
    }


def test_malformed_active_supply_count_fails_closed_instead_of_crashing() -> None:
    previous = _state(fair_value=100.0, active_count=2)
    current = _state(fair_value=120.0, active_count="not-a-number")

    delta = build_reconstruction_delta(previous, current)

    assert "accepted_active_count_invalid" in delta["quality_change_reasons"]
    assert "active_supply_changed" not in delta["valuation_change_reasons"]
    assert delta["valuation_input_change"] is False
    assert delta["reconstruction_health_failure"] is True


def test_negative_active_supply_count_cannot_legitimize_repricing() -> None:
    previous = _state(fair_value=100.0, active_count=2)
    current = _state(fair_value=120.0, active_count=-1)

    delta = build_reconstruction_delta(previous, current)

    assert "accepted_active_count_invalid" in delta["quality_change_reasons"]
    assert "active_supply_changed_without_trusted_metadata" in delta["quality_change_reasons"]
    assert "active_supply_changed" not in delta["valuation_change_reasons"]
    assert delta["valuation_input_change"] is False
    assert delta["reconstruction_health_failure"] is True


def test_valid_active_supply_change_remains_valuation_evidence() -> None:
    previous = _state(fair_value=100.0, active_count=2)
    current = _state(fair_value=120.0, active_count=3)

    delta = build_reconstruction_delta(previous, current)

    assert "accepted_active_count_invalid" not in delta["quality_change_reasons"]
    assert "active_supply_changed" in delta["valuation_change_reasons"]
    assert delta["valuation_input_change"] is True
    assert delta["reconstruction_health_failure"] is False
