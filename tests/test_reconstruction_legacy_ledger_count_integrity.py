from reconstruction import build_reconstruction_delta


def _state(*, fair_value: float, accepted_sales_total: int, accepted_ids: list[str]):
    return {
        "card_id": "card-1",
        "run_id": f"run-{fair_value}",
        "last_updated": "2026-08-22T00:00:00Z",
        "fair_value": fair_value,
        "accepted_sales_total": accepted_sales_total,
        "latest_sale_date": "2026-08-21",
        "accepted_active_count": 0,
        "lowest_ask": None,
        "median_ask": None,
        "evidence_grade": "A",
        "confidence": 0.9,
        "evidence_ledger": {
            # Legacy ledgers intentionally omit accepted_total.
            "accepted": [
                {
                    "evidence_id": evidence_id,
                    "title": "2025 Topps Chrome Example PSA 10",
                    "price": "100.00",
                    "currency": "USD",
                    "event_date": "2026-08-21",
                    "source": "ebay_product_research",
                    "url": f"https://www.ebay.com/itm/{index + 1000}",
                }
                for index, evidence_id in enumerate(accepted_ids)
            ]
        },
    }


def test_legacy_ledger_state_count_mismatch_fails_closed():
    previous = _state(fair_value=100.0, accepted_sales_total=1, accepted_ids=["sale-1"])
    current = _state(fair_value=120.0, accepted_sales_total=2, accepted_ids=["sale-1"])

    delta = build_reconstruction_delta(previous, current)

    assert "accepted_comp_ledger_invalid" in delta["quality_change_reasons"]
    assert "accepted_sales_changed_without_trusted_lineage" in delta["quality_change_reasons"]
    assert delta["valuation_input_change"] is False
    assert delta["reconstruction_health_failure"] is True


def test_legacy_ledger_matching_state_count_remains_trusted():
    previous = _state(fair_value=100.0, accepted_sales_total=1, accepted_ids=["sale-1"])
    current = _state(
        fair_value=120.0,
        accepted_sales_total=2,
        accepted_ids=["sale-1", "sale-2"],
    )

    delta = build_reconstruction_delta(previous, current)

    assert "accepted_comp_set_changed" in delta["valuation_change_reasons"]
    assert "accepted_comp_ledger_invalid" not in delta["quality_change_reasons"]
    assert delta["valuation_input_change"] is True
    assert delta["reconstruction_health_failure"] is False
