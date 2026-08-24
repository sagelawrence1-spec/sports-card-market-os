from calibration_safety import assess_calibration_safety


def valid_benchmark() -> dict:
    return {
        "production_ready": True,
        "lift": {
            "mae_improvement_pct": 0.2,
            "directional_accuracy_lift": 0.05,
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


def test_malformed_lift_container_fails_closed_instead_of_raising():
    benchmark = valid_benchmark()
    benchmark["lift"] = ["not", "a", "mapping"]

    result = assess_calibration_safety(benchmark)

    assert result["calibration_review_allowed"] is False
    assert "invalid_lift_container" in result["blockers"]
    assert "missing_net_mae_lift" in result["blockers"]
    assert "missing_directional_lift" in result["blockers"]


def test_malformed_segments_container_fails_closed_instead_of_raising():
    benchmark = valid_benchmark()
    benchmark["segments"] = "corrupt"

    result = assess_calibration_safety(benchmark)

    assert result["calibration_review_allowed"] is False
    assert "invalid_evidence_grade_observations:A" in result["blockers"]
    assert "invalid_evidence_grade_observations:B" in result["blockers"]
    assert "invalid_confidence_band_observations:high" in result["blockers"]
    assert "invalid_confidence_band_observations:medium" in result["blockers"]


def test_malformed_segment_family_fails_closed_instead_of_raising():
    benchmark = valid_benchmark()
    benchmark["segments"]["evidence_grade"] = ["corrupt"]

    result = assess_calibration_safety(benchmark)

    assert result["calibration_review_allowed"] is False
    assert "invalid_evidence_grade_observations:A" in result["blockers"]
    assert "invalid_evidence_grade_observations:B" in result["blockers"]


def test_missing_segment_family_remains_underpowered_not_malformed():
    benchmark = valid_benchmark()
    del benchmark["segments"]["evidence_grade"]

    result = assess_calibration_safety(benchmark)

    assert "underpowered_evidence_grade:A" in result["blockers"]
    assert "underpowered_evidence_grade:B" in result["blockers"]
    assert not any(
        blocker.startswith("invalid_evidence_grade_observations:")
        for blocker in result["blockers"]
    )
