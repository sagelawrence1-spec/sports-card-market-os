import pytest

from reconstruction import build_reconstruction_delta, build_reconstruction_record


def state(**overrides):
    base={
        "card_id":"card-1",
        "run_id":"run-2",
        "last_updated":"2026-08-12T12:00:00Z",
        "fair_value":100.0,
        "accepted_sales_total":10,
        "latest_sale_date":"2026-08-11",
        "accepted_active_count":2,
        "lowest_ask":120.0,
        "median_ask":130.0,
        "evidence_grade":"A",
        "confidence":0.8,
        "evidence_ledger":{
            "accepted":[
                {"evidence_id":"sale-1"},
                {"evidence_id":"sale-2"},
            ]
        },
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
        state(
            fair_value=120.0,
            accepted_sales_total=11,
            latest_sale_date="2026-08-12",
            evidence_ledger={"accepted":[{"evidence_id":"sale-1"},{"evidence_id":"sale-2"},{"evidence_id":"sale-3"}]},
        ),
    )
    assert delta["material_input_change"] is True
    assert delta["valuation_input_change"] is True
    assert "accepted_sales_changed" in delta["valuation_change_reasons"]
    assert "accepted_comp_set_changed" in delta["valuation_change_reasons"]
    assert "latest_sale_changed" in delta["valuation_change_reasons"]
    assert delta["unexplained_repricing"] is False
    assert delta["reconstruction_health_failure"] is False


def test_same_count_comp_replacement_explains_repricing():
    delta=build_reconstruction_delta(
        state(),
        state(
            fair_value=116.0,
            evidence_ledger={"accepted":[{"evidence_id":"sale-1"},{"evidence_id":"sale-3"}]},
        ),
    )
    assert delta["accepted_sales_delta"] == 0
    assert delta["valuation_change_reasons"] == ["accepted_comp_set_changed"]
    assert delta["valuation_input_change"] is True
    assert delta["reconstruction_health_failure"] is False


def test_empty_comp_set_change_is_still_attributed_when_ledgers_exist():
    delta=build_reconstruction_delta(
        state(),
        state(fair_value=116.0,evidence_ledger={"accepted":[]}),
    )
    assert delta["valuation_change_reasons"] == ["accepted_comp_set_changed"]
    assert delta["valuation_input_change"] is True
    assert delta["reconstruction_health_failure"] is False


def test_comp_ledger_disappearance_cannot_explain_large_repricing():
    current=state(fair_value=116.0)
    current.pop("evidence_ledger")
    delta=build_reconstruction_delta(state(),current)
    assert delta["valuation_change_reasons"] == []
    assert delta["quality_change_reasons"] == ["accepted_comp_ledger_presence_changed"]
    assert delta["valuation_input_change"] is False
    assert delta["unexplained_repricing"] is True
    assert delta["reconstruction_health_failure"] is True


def test_supply_or_confidence_change_is_attributed():
    delta=build_reconstruction_delta(
        state(),
        state(fair_value=116.0,accepted_active_count=4,confidence=0.9),
    )
    assert "active_supply_changed" in delta["valuation_change_reasons"]
    assert "confidence_changed" in delta["quality_change_reasons"]
    assert delta["valuation_input_change"] is True
    assert delta["reconstruction_health_failure"] is False


def test_ask_price_change_with_same_listing_count_explains_repricing():
    delta=build_reconstruction_delta(
        state(),
        state(fair_value=116.0,lowest_ask=110.0,median_ask=125.0),
    )
    assert delta["active_supply_delta"] == 0
    assert "lowest_ask_changed" in delta["valuation_change_reasons"]
    assert "median_ask_changed" in delta["valuation_change_reasons"]
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


def test_reconstruction_record_captures_stable_lineage():
    previous=state(run_id="run-1",last_updated="2026-08-11T12:00:00Z")
    current=state(run_id="run-2",last_updated="2026-08-12T12:00:00Z",fair_value=110.0,accepted_sales_total=11)
    record=build_reconstruction_record(previous,current)
    assert record["schema"] == "market-reconstruction.v1"
    assert record["record_id"] == "card-1:run-1->run-2"
    assert record["previous_run_id"] == "run-1"
    assert record["run_id"] == "run-2"
    assert record["previous_as_of"] == "2026-08-11T12:00:00Z"
    assert record["as_of"] == "2026-08-12T12:00:00Z"
    assert record["delta"]["accepted_sales_delta"] == 1


def test_initial_reconstruction_record_has_explicit_initial_lineage():
    record=build_reconstruction_record(None,state())
    assert record["record_id"] == "card-1:initial->run-2"
    assert record["previous_run_id"] is None
    assert record["previous_as_of"] is None
    assert record["delta"]["has_previous"] is False


def test_reconstruction_record_rejects_cross_card_lineage():
    previous=state(card_id="card-2",run_id="run-1",last_updated="2026-08-11T12:00:00Z")
    with pytest.raises(ValueError,match="same card"):
        build_reconstruction_record(previous,state())


def test_reconstruction_record_rejects_same_run_lineage():
    previous=state(run_id="run-2",last_updated="2026-08-11T12:00:00Z")
    with pytest.raises(ValueError,match="different runs"):
        build_reconstruction_record(previous,state())


def test_reconstruction_record_rejects_nonchronological_lineage():
    previous=state(run_id="run-1",last_updated="2026-08-13T12:00:00Z")
    with pytest.raises(ValueError,match="strictly earlier"):
        build_reconstruction_record(previous,state())


def test_reconstruction_record_requires_current_lineage_fields():
    with pytest.raises(ValueError,match="card_id, run_id, and last_updated"):
        build_reconstruction_record(None,state(run_id=""))
