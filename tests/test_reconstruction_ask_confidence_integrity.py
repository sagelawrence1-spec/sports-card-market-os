from reconstruction import build_reconstruction_delta


def _state(**overrides):
    base = {
        "card_id": "card-1",
        "run_id": "run-2",
        "last_updated": "2026-08-23T00:00:00Z",
        "fair_value": 100.0,
        "accepted_sales_total": 0,
        "latest_sale_date": None,
        "accepted_active_count": 2,
        "lowest_ask": 120.0,
        "median_ask": 130.0,
        "evidence_grade": "A",
        "confidence": 0.8,
        "evidence_ledger": {"accepted_total": 0, "accepted": []},
    }
    base.update(overrides)
    return base


def test_malformed_lowest_ask_cannot_legitimize_repricing() -> None:
    delta = build_reconstruction_delta(
        _state(),
        _state(fair_value=120.0, lowest_ask="not-a-price"),
    )

    assert "lowest_ask_invalid" in delta["quality_change_reasons"]
    assert "lowest_ask_changed_without_trusted_metadata" in delta["quality_change_reasons"]
    assert "lowest_ask_changed" not in delta["valuation_change_reasons"]
    assert delta["valuation_input_change"] is False
    assert delta["reconstruction_health_failure"] is True


def test_negative_or_nonfinite_median_ask_fails_closed() -> None:
    for bad_value in (-1, float("inf"), float("nan")):
        delta = build_reconstruction_delta(
            _state(),
            _state(fair_value=120.0, median_ask=bad_value),
        )

        assert "median_ask_invalid" in delta["quality_change_reasons"]
        assert "median_ask_changed_without_trusted_metadata" in delta["quality_change_reasons"]
        assert "median_ask_changed" not in delta["valuation_change_reasons"]
        assert delta["reconstruction_health_failure"] is True


def test_valid_ask_price_change_remains_valuation_evidence() -> None:
    delta = build_reconstruction_delta(
        _state(),
        _state(fair_value=120.0, lowest_ask="125.00", median_ask=135),
    )

    assert delta["valuation_change_reasons"] == ["lowest_ask_changed", "median_ask_changed"]
    assert "lowest_ask_invalid" not in delta["quality_change_reasons"]
    assert "median_ask_invalid" not in delta["quality_change_reasons"]
    assert delta["valuation_input_change"] is True
    assert delta["reconstruction_health_failure"] is False


def test_malformed_or_out_of_range_confidence_fails_closed_without_crashing() -> None:
    for bad_value in ("not-a-number", -0.1, 1.1, float("inf"), float("nan"), True):
        delta = build_reconstruction_delta(
            _state(),
            _state(fair_value=120.0, confidence=bad_value),
        )

        assert "confidence_invalid" in delta["quality_change_reasons"]
        assert "confidence_changed" not in delta["quality_change_reasons"]
        assert delta["valuation_input_change"] is False
        assert delta["reconstruction_health_failure"] is True


def test_valid_confidence_change_remains_quality_only() -> None:
    delta = build_reconstruction_delta(
        _state(),
        _state(confidence="0.90"),
    )

    assert "confidence_invalid" not in delta["quality_change_reasons"]
    assert "confidence_changed" in delta["quality_change_reasons"]
    assert delta["confidence_delta"] == 0.09999999999999998
    assert delta["valuation_input_change"] is False
