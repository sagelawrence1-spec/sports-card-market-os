from calibration_safety import CalibrationSafetyPolicy, assess_calibration_safety


def sample(ready=True, mae=0.2, direction=0.05, a=12, b=11, high=13, medium=10):
    return {
        "production_ready": ready,
        "lift": {"mae_improvement_pct": mae, "directional_accuracy_lift": direction},
        "segments": {
            "evidence_grade": {"A": {"observations": a}, "B": {"observations": b}},
            "confidence_band": {"high": {"observations": high}, "medium": {"observations": medium}},
        },
    }


def test_good_sample_allows_review():
    result = assess_calibration_safety(sample())
    assert result["calibration_review_allowed"] is True
    assert result["automatic_threshold_changes_allowed"] is False


def test_not_ready_blocks_review():
    result = assess_calibration_safety(sample(ready=False))
    assert "benchmark_not_production_ready" in result["blockers"]


def test_missing_production_ready_blocks_review():
    benchmark = sample()
    benchmark.pop("production_ready")
    result = assess_calibration_safety(benchmark)
    assert "benchmark_not_production_ready" in result["blockers"]
    assert result["calibration_review_allowed"] is False


def test_truthy_string_production_ready_fails_closed():
    result = assess_calibration_safety(sample(ready="false"))
    assert "invalid_production_ready" in result["blockers"]
    assert result["calibration_review_allowed"] is False


def test_numeric_production_ready_fails_closed():
    result = assess_calibration_safety(sample(ready=1))
    assert "invalid_production_ready" in result["blockers"]
    assert result["calibration_review_allowed"] is False


def test_no_mae_lift_blocks_review():
    result = assess_calibration_safety(sample(mae=0.0))
    assert "non_positive_net_mae_lift" in result["blockers"]


def test_negative_direction_blocks_review():
    result = assess_calibration_safety(sample(direction=-0.01))
    assert "negative_directional_lift" in result["blockers"]


def test_small_segments_block_review():
    result = assess_calibration_safety(sample(b=4, medium=3))
    assert "underpowered_evidence_grade:B" in result["blockers"]
    assert "underpowered_confidence_band:medium" in result["blockers"]


def test_custom_policy_can_be_stricter():
    policy = CalibrationSafetyPolicy(
        min_mae_improvement_pct=0.15,
        min_directional_accuracy_lift=0.02,
        min_segment_samples=20,
        required_evidence_grades=("A",),
        required_confidence_bands=("high",),
    )
    result = assess_calibration_safety(sample(mae=0.25, direction=0.04, a=25, high=21), policy=policy)
    assert result["calibration_review_allowed"] is True
