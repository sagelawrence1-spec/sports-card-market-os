from reconstruction import build_reconstruction_delta


def state(**overrides):
    base={
        "last_updated":"2026-08-12T12:00:00Z",
        "fair_value":100.0,
        "accepted_sales_total":10,
        "latest_sale_date":"2026-08-11",
        "accepted_active_count":2,
        "evidence_grade":"A",
        "confidence":0.8,
    }
    base.update(overrides)
    return base


def test_initial_observation_is_not_suspicious():
    delta=build_reconstruction_delta(None,state())
    assert delta["has_previous"] is False
    assert delta["valuation_input_change"] is True
    assert delta["unexplained_repricing"] is False
    assert delta["reconstruction_health_failure"] is False


def test_eight_percent_move_without_input_change_is_flagged():
    delta=build_reconstruction_delta(state(),state(fair_value=108.0))
    assert delta["material_input_change"] is False
    assert delta["valuation_input_change"] is False
    assert delta["unexplained_repricing"] is True
    assert delta["reconstruction_health_failure"] is False


def test_fifteen_percent_move_without_input_change_fails_closed():
    delta=build_reconstruction_delta(state(),state(fair_value=115.0))
    assert delta["unexplained_repricing"] is True
    assert delta["reconstruction_health_failure"] is True


def test_new_sale_explains_repricing():
    delta=build_reconstruction_delta(
        state(),
        state(fair_value=120.0,accepted_sales_total=11,latest_sale_date="2026-08-12"),
    )
    assert delta["material_input_change"] is True
    assert delta["valuation_input_change"] is True
    assert "accepted_sales_changed" in delta["valuation_change_reasons"]
    assert "latest_sale_changed" in delta["valuation_change_reasons"]
    assert delta["unexplained_repricing"] is False
    assert delta["reconstruction_health_failure"] is False


def test_supply_or_confidence_change_is_attributed():
    delta=build_reconstruction_delta(
        state(),
        state(fair_value=116.0,accepted_active_count=4,confidence=0.9),
    )
    assert "active_supply_changed" in delta["valuation_change_reasons"]
    assert "confidence_changed" in delta["quality_change_reasons"]
    assert delta["valuation_input_change"] is True
    assert delta["reconstruction_health_failure"] is False


def test_confidence_change_alone_cannot_explain_large_repricing():
    delta=build_reconstruction_delta(
        state(),
        state(fair_value=116.0,confidence=0.9),
    )
    assert delta["material_input_change"] is True
    assert delta["valuation_input_change"] is False
    assert delta["valuation_change_reasons"] == []
    assert delta["quality_change_reasons"] == ["confidence_changed"]
    assert delta["unexplained_repricing"] is True
    assert delta["reconstruction_health_failure"] is True


def test_evidence_grade_change_alone_cannot_explain_large_repricing():
    delta=build_reconstruction_delta(
        state(),
        state(fair_value=116.0,evidence_grade="B"),
    )
    assert delta["material_input_change"] is True
    assert delta["valuation_input_change"] is False
    assert delta["quality_change_reasons"] == ["evidence_grade_changed"]
    assert delta["unexplained_repricing"] is True
    assert delta["reconstruction_health_failure"] is True
