from reconstruction import build_reconstruction_delta


def state(**overrides):
    base = {
        "card_id": "card-1",
        "run_id": "run-2",
        "last_updated": "2026-08-23T08:00:00Z",
        "fair_value": 100.0,
        "accepted_sales_total": 2,
        "latest_sale_date": "2026-08-22",
        "accepted_active_count": 2,
        "lowest_ask": 120.0,
        "median_ask": 130.0,
        "evidence_grade": "A",
        "confidence": 0.8,
        "evidence_ledger": {
            "accepted": [
                {"evidence_id": "sale-1", "event_date": "2026-08-21"},
                {"evidence_id": "sale-2", "event_date": "2026-08-22"},
            ]
        },
    }
    base.update(overrides)
    return base


def test_malformed_current_fair_value_fails_closed_without_crashing():
    delta = build_reconstruction_delta(state(), state(fair_value="not-a-number"))
    assert delta["fair_value_change_pct"] is None
    assert delta["quality_change_reasons"] == ["fair_value_invalid"]
    assert delta["reconstruction_health_failure"] is True


def test_non_finite_fair_value_fails_closed():
    for value in (float("nan"), float("inf"), float("-inf")):
        delta = build_reconstruction_delta(state(), state(fair_value=value))
        assert delta["fair_value_change_pct"] is None
        assert "fair_value_invalid" in delta["quality_change_reasons"]
        assert delta["reconstruction_health_failure"] is True


def test_zero_and_negative_fair_values_fail_closed():
    for value in (0, -1, -100.0):
        delta = build_reconstruction_delta(state(), state(fair_value=value))
        assert delta["fair_value_change_pct"] is None
        assert "fair_value_invalid" in delta["quality_change_reasons"]
        assert delta["reconstruction_health_failure"] is True


def test_invalid_previous_fair_value_fails_closed():
    delta = build_reconstruction_delta(state(fair_value=None), state())
    assert delta["fair_value_change_pct"] is None
    assert "fair_value_invalid" in delta["quality_change_reasons"]
    assert delta["reconstruction_health_failure"] is True


def test_invalid_initial_fair_value_is_not_treated_as_healthy_initial_observation():
    delta = build_reconstruction_delta(None, state(fair_value="bad"))
    assert delta["has_previous"] is False
    assert delta["valuation_input_change"] is False
    assert delta["quality_change_reasons"] == ["fair_value_invalid"]
    assert delta["reconstruction_health_failure"] is True


def test_valid_numeric_string_fair_values_remain_supported():
    delta = build_reconstruction_delta(state(fair_value="100.0"), state(fair_value="110.0"))
    assert delta["fair_value_change_pct"] == 0.1
    assert "fair_value_invalid" not in delta["quality_change_reasons"]
    assert delta["unexplained_repricing"] is True
    assert delta["reconstruction_health_failure"] is False
