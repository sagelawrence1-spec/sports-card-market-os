from calibration_safety import assess_calibration_safety


def sample(*, a=12, b=11, high=13, medium=10):
    return {
        "production_ready": True,
        "lift": {
            "mae_improvement_pct": 0.2,
            "directional_accuracy_lift": 0.05,
        },
        "segments": {
            "evidence_grade": {
                "A": {"observations": a},
                "B": {"observations": b},
            },
            "confidence_band": {
                "high": {"observations": high},
                "medium": {"observations": medium},
            },
        },
    }


def test_fractional_required_segment_count_fails_closed():
    result = assess_calibration_safety(sample(a=12.9))

    assert result["calibration_review_allowed"] is False
    assert "invalid_evidence_grade_observations:A" in result["blockers"]


def test_boolean_required_segment_count_fails_closed():
    result = assess_calibration_safety(sample(high=True))

    assert result["calibration_review_allowed"] is False
    assert "invalid_confidence_band_observations:high" in result["blockers"]


def test_negative_required_segment_count_fails_closed():
    result = assess_calibration_safety(sample(b=-11))

    assert result["calibration_review_allowed"] is False
    assert "invalid_evidence_grade_observations:B" in result["blockers"]


def test_digit_only_persisted_segment_count_remains_supported():
    result = assess_calibration_safety(sample(a="12", b="11", high="13", medium="10"))

    assert result["calibration_review_allowed"] is True


def test_malformed_unknown_segment_count_blocks_packet():
    benchmark = sample()
    benchmark["segments"]["evidence_grade"]["unknown"] = {"observations": "10.5"}

    result = assess_calibration_safety(benchmark)

    assert result["calibration_review_allowed"] is False
    assert "invalid_evidence_grade_observations:unknown" in result["blockers"]
