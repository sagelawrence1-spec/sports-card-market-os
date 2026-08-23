from calibration_safety import assess_calibration_safety


def _benchmark(mae_lift=0.2, directional_lift=0.05):
    return {
        "production_ready": True,
        "lift": {
            "mae_improvement_pct": mae_lift,
            "directional_accuracy_lift": directional_lift,
        },
        "segments": {
            "evidence_grade": {
                "A": {"observations": 20},
                "B": {"observations": 20},
            },
            "confidence_band": {
                "high": {"observations": 20},
                "medium": {"observations": 20},
            },
        },
    }


def test_nan_mae_lift_fails_closed():
    result = assess_calibration_safety(_benchmark(mae_lift=float("nan")))

    assert result["calibration_review_allowed"] is False
    assert "invalid_net_mae_lift" in result["blockers"]


def test_infinite_directional_lift_fails_closed():
    result = assess_calibration_safety(_benchmark(directional_lift=float("inf")))

    assert result["calibration_review_allowed"] is False
    assert "invalid_directional_lift" in result["blockers"]


def test_non_numeric_lifts_fail_closed_instead_of_raising():
    result = assess_calibration_safety(_benchmark(mae_lift="not-a-number", directional_lift={}))

    assert result["calibration_review_allowed"] is False
    assert "invalid_net_mae_lift" in result["blockers"]
    assert "invalid_directional_lift" in result["blockers"]


def test_finite_numeric_string_lifts_remain_supported():
    result = assess_calibration_safety(_benchmark(mae_lift="0.20", directional_lift="0.05"))

    assert result["calibration_review_allowed"] is True
    assert result["blockers"] == []
