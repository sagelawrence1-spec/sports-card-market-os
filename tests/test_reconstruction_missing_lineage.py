from reconstruction import build_reconstruction_delta


def state(**overrides):
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
    }
    base.update(overrides)
    return base


def test_sold_changes_without_either_comp_ledger_cannot_explain_repricing():
    delta = build_reconstruction_delta(
        state(),
        state(
            fair_value=116.0,
            accepted_sales_total=11,
            latest_sale_date="2026-08-12",
        ),
    )

    assert delta["valuation_change_reasons"] == []
    assert delta["quality_change_reasons"] == [
        "accepted_sales_changed_without_trusted_lineage",
        "latest_sale_changed_without_trusted_lineage",
    ]
    assert delta["valuation_input_change"] is False
    assert delta["unexplained_repricing"] is True
    assert delta["reconstruction_health_failure"] is True


def test_independent_supply_change_still_explains_repricing_without_sold_lineage():
    delta = build_reconstruction_delta(
        state(),
        state(
            fair_value=116.0,
            accepted_sales_total=11,
            latest_sale_date="2026-08-12",
            accepted_active_count=4,
        ),
    )

    assert delta["valuation_change_reasons"] == ["active_supply_changed"]
    assert delta["quality_change_reasons"] == [
        "accepted_sales_changed_without_trusted_lineage",
        "latest_sale_changed_without_trusted_lineage",
    ]
    assert delta["valuation_input_change"] is True
    assert delta["unexplained_repricing"] is False
    assert delta["reconstruction_health_failure"] is False
