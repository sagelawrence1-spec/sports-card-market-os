from reconstruction import build_reconstruction_delta


def state(**overrides):
    base = {
        "card_id": "card-1",
        "run_id": "run-2",
        "last_updated": "2026-08-23T09:00:00Z",
        "fair_value": None,
        "accepted_sales_total": 0,
        "latest_sale_date": None,
        "accepted_active_count": 0,
        "lowest_ask": None,
        "median_ask": None,
        "evidence_grade": "F",
        "confidence": 0.0,
        "engine_classification": "NOT_ENOUGH_EVIDENCE",
        "evidence_ledger": {"accepted": [], "accepted_total": 0},
    }
    base.update(overrides)
    return base


def test_intentionally_withheld_initial_fair_value_is_healthy_unvalued_state():
    delta = build_reconstruction_delta(None, state())
    assert delta["has_previous"] is False
    assert delta["fair_value_change_pct"] is None
    assert delta["reconstruction_health_failure"] is False
    assert delta["unexplained_repricing"] is False


def test_withheld_to_withheld_does_not_create_false_repricing_or_health_failure():
    previous = state(run_id="run-1", last_updated="2026-08-22T09:00:00Z")
    current = state()
    delta = build_reconstruction_delta(previous, current)
    assert delta["has_previous"] is True
    assert delta["fair_value_change_pct"] is None
    assert delta["valuation_input_change"] is False
    assert delta["unexplained_repricing"] is False
    assert delta["reconstruction_health_failure"] is False
