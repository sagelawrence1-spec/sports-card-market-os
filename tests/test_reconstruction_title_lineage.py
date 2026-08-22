from reconstruction import build_reconstruction_delta


def _state(*, fair_value=100.0, title="2025 Topps Chrome Shohei Ohtani #1 PSA 10"):
    return {
        "card_id": "card-1",
        "run_id": "run-1",
        "last_updated": "2026-08-22T12:00:00Z",
        "fair_value": fair_value,
        "accepted_sales_total": 1,
        "latest_sale_date": "2026-08-20",
        "accepted_active_count": 0,
        "lowest_ask": None,
        "median_ask": None,
        "evidence_grade": "A",
        "confidence": 0.9,
        "evidence_ledger": {
            "accepted": [
                {
                    "evidence_id": "ebay_product_research:123:2026-08-20",
                    "title": title,
                    "price": 100.0,
                    "currency": "USD",
                    "event_date": "2026-08-20",
                    "source": "eBay Product Research",
                    "url": "https://www.ebay.com/itm/123",
                }
            ]
        },
    }


def test_same_evidence_id_title_mutation_is_integrity_change_not_valuation_evidence():
    previous = _state()
    current = _state(
        fair_value=116.0,
        title="2025 Topps Chrome Shohei Ohtani #1 Gold Refractor PSA 10",
    )

    delta = build_reconstruction_delta(previous, current)

    assert delta["valuation_change_reasons"] == []
    assert delta["quality_change_reasons"] == ["accepted_comp_content_changed"]
    assert delta["valuation_input_change"] is False
    assert delta["unexplained_repricing"] is True
    assert delta["reconstruction_health_failure"] is True


def test_identical_title_lineage_remains_stable():
    delta = build_reconstruction_delta(_state(), _state())

    assert delta["material_input_change"] is False
    assert delta["change_reasons"] == ["no_material_input_change"]
