from reconstruction import build_reconstruction_delta


def _state(**overrides):
    base = {
        "card_id": "card-1",
        "run_id": "run-2",
        "last_updated": "2026-08-12T12:00:00Z",
        "fair_value": 100.0,
        "accepted_sales_total": 10,
        "latest_sale_date": "2026-08-11",
        "accepted_active_count": 2,
        "lowest_ask": 120.0,
        "median_ask": 130.0,
        "evidence_grade": "A",
        "confidence": 0.8,
        "evidence_ledger": {
            "accepted": [
                {"evidence_id": "sale-1"},
                {"evidence_id": "sale-2"},
            ]
        },
    }
    base.update(overrides)
    return base


def test_invalid_comp_ledger_cannot_let_sale_count_or_latest_date_justify_repricing():
    current = _state(
        fair_value=116.0,
        accepted_sales_total=11,
        latest_sale_date="2026-08-12",
        evidence_ledger={"accepted": [{"evidence_id": "sale-1"}, {"evidence_id": ""}]},
    )

    delta = build_reconstruction_delta(_state(), current)

    assert delta["valuation_change_reasons"] == []
    assert delta["quality_change_reasons"] == [
        "accepted_comp_ledger_invalid",
        "accepted_sales_changed_without_trusted_lineage",
        "latest_sale_changed_without_trusted_lineage",
    ]
    assert delta["valuation_input_change"] is False
    assert delta["unexplained_repricing"] is True
    assert delta["reconstruction_health_failure"] is True


def test_comp_ledger_disappearance_suppresses_sold_derived_repricing_reasons():
    current = _state(
        fair_value=116.0,
        accepted_sales_total=11,
        latest_sale_date="2026-08-12",
    )
    current.pop("evidence_ledger")

    delta = build_reconstruction_delta(_state(), current)

    assert delta["valuation_change_reasons"] == []
    assert delta["quality_change_reasons"] == [
        "accepted_comp_ledger_presence_changed",
        "accepted_sales_changed_without_trusted_lineage",
        "latest_sale_changed_without_trusted_lineage",
    ]
    assert delta["reconstruction_health_failure"] is True


def test_independent_supply_change_can_still_explain_repricing_when_sold_lineage_fails():
    current = _state(
        fair_value=116.0,
        accepted_sales_total=11,
        latest_sale_date="2026-08-12",
        accepted_active_count=3,
        evidence_ledger={"accepted": "corrupt"},
    )

    delta = build_reconstruction_delta(_state(), current)

    assert delta["valuation_change_reasons"] == ["active_supply_changed"]
    assert "accepted_comp_ledger_invalid" in delta["quality_change_reasons"]
    assert "accepted_sales_changed_without_trusted_lineage" in delta["quality_change_reasons"]
    assert "latest_sale_changed_without_trusted_lineage" in delta["quality_change_reasons"]
    assert delta["valuation_input_change"] is True
    assert delta["unexplained_repricing"] is False
    assert delta["reconstruction_health_failure"] is False
