from calibration_safety import assess_calibration_safety


def test_non_mapping_benchmark_fails_closed_without_raising():
    for benchmark in (None, [], "benchmark", 1, True):
        result = assess_calibration_safety(benchmark)  # type: ignore[arg-type]

        assert result["calibration_review_allowed"] is False
        assert result["automatic_threshold_changes_allowed"] is False
        assert result["decision"] == "blocked"
        assert result["blockers"] == ["invalid_benchmark_container"]
        assert result["warnings"] == []


def test_invalid_benchmark_still_reports_effective_policy():
    result = assess_calibration_safety(None)  # type: ignore[arg-type]

    assert result["policy"]["min_segment_samples"] == 10
    assert result["policy"]["required_evidence_grades"] == ["A", "B"]
    assert result["policy"]["required_confidence_bands"] == ["high", "medium"]
