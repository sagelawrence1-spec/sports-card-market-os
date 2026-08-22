from reconstruction import build_reconstruction_delta


def _state(*, fair_value=100.0, evidence_ledger=None):
    return {
        "card_id": "card-1",
        "run_id": "run-2",
        "last_updated": "2026-08-12T12:00:00Z",
        "fair_value": fair_value,
        "accepted_sales_total": 2,
        "latest_sale_date": "2026-08-11",
        "accepted_active_count": 2,
        "lowest_ask": 120.0,
        "median_ask": 130.0,
        "evidence_grade": "A",
        "confidence": 0.8,
        "evidence_ledger": evidence_ledger
        if evidence_ledger is not None
        else {
            "accepted": [
                {"evidence_id": "sale-1"},
                {"evidence_id": "sale-2"},
            ]
        },
    }


def test_malformed_accepted_row_cannot_be_silently_skipped_from_lineage():
    current_ledger = {
        "accepted": [
            {"evidence_id": "sale-1"},
            {"evidence_id": "sale-2"},
            "corrupt-row",
        ]
    }
    delta = build_reconstruction_delta(
        _state(),
        _state(fair_value=116.0, evidence_ledger=current_ledger),
    )

    assert delta["valuation_change_reasons"] == []
    assert delta["quality_change_reasons"] == ["accepted_comp_ledger_invalid"]
    assert delta["valuation_input_change"] is False
    assert delta["unexplained_repricing"] is True
    assert delta["reconstruction_health_failure"] is True


def test_duplicate_evidence_ids_make_accepted_comp_ledger_invalid():
    current_ledger = {
        "accepted": [
            {"evidence_id": "sale-1"},
            {"evidence_id": "sale-2"},
            {"evidence_id": "sale-2"},
        ]
    }
    delta = build_reconstruction_delta(
        _state(),
        _state(fair_value=116.0, evidence_ledger=current_ledger),
    )

    assert delta["valuation_change_reasons"] == []
    assert delta["quality_change_reasons"] == ["accepted_comp_ledger_invalid"]
    assert delta["valuation_input_change"] is False
    assert delta["reconstruction_health_failure"] is True


def test_blank_evidence_id_makes_accepted_comp_ledger_invalid():
    current_ledger = {
        "accepted": [
            {"evidence_id": "sale-1"},
            {"evidence_id": "   "},
        ]
    }
    delta = build_reconstruction_delta(
        _state(),
        _state(evidence_ledger=current_ledger),
    )

    assert delta["quality_change_reasons"] == ["accepted_comp_ledger_invalid"]
    assert delta["material_input_change"] is True
    assert delta["valuation_input_change"] is False
