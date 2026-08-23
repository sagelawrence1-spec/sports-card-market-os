from calibration_safety import assess_calibration_history


def _run(outer_day: str | None, result_day: str | None, mature: int) -> dict:
    result = {
        "production_ready": True,
        "mature_observations": mature,
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
    if result_day is not None:
        result["evaluation_date"] = result_day
    run = {"result": result}
    if outer_day is not None:
        run["evaluated_at"] = outer_day
    return run


def test_wrapper_date_cannot_rewrite_result_checkpoint_date():
    result = assess_calibration_history(
        [
            _run("2026-06-01", "2026-06-01", 20),
            _run("2026-07-01", "2026-06-15", 28),
            _run("2026-08-01", "2026-08-01", 36),
        ]
    )

    assert result["calibration_review_allowed"] is False
    assert "invalid_evaluation_date:1" in result["blockers"]
    assert result["checkpoints_seen"] == 2


def test_matching_wrapper_and_result_dates_remain_valid():
    result = assess_calibration_history(
        [
            _run("2026-06-01", "2026-06-01", 20),
            _run("2026-07-01", "2026-07-01", 28),
            _run("2026-08-01", "2026-08-01", 36),
        ]
    )

    assert result["calibration_review_allowed"] is True
    assert result["blockers"] == []


def test_single_date_source_remains_backward_compatible():
    result = assess_calibration_history(
        [
            _run("2026-06-01", None, 20),
            _run(None, "2026-07-01", 28),
            _run("2026-08-01", "2026-08-01", 36),
        ]
    )

    assert result["calibration_review_allowed"] is True


def test_trailing_garbage_cannot_be_truncated_into_valid_checkpoint_date():
    result = assess_calibration_history(
        [
            _run("2026-06-01", "2026-06-01", 20),
            _run("2026-07-01garbage", "2026-07-01garbage", 28),
            _run("2026-08-01", "2026-08-01", 36),
        ]
    )

    assert result["calibration_review_allowed"] is False
    assert "invalid_evaluation_date:1" in result["blockers"]
    assert result["checkpoints_seen"] == 2


def test_real_iso_datetime_checkpoint_remains_supported():
    result = assess_calibration_history(
        [
            _run("2026-06-01T08:30:00Z", "2026-06-01", 20),
            _run("2026-07-01T15:45:00+00:00", "2026-07-01", 28),
            _run("2026-08-01", "2026-08-01", 36),
        ]
    )

    assert result["calibration_review_allowed"] is True
    assert result["blockers"] == []
