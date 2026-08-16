from calibration_safety import (
    CalibrationSafetyPolicy,
    assess_calibration_history,
)


def benchmark_run(day: str, mature: int, *, mae: float = 0.2, direction: float = 0.05):
    return {
        "evaluated_at": day,
        "result": {
            "evaluation_date": day,
            "production_ready": True,
            "mature_observations": mature,
            "lift": {
                "mae_improvement_pct": mae,
                "directional_accuracy_lift": direction,
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
        },
    }


def test_repeated_newly_matured_checkpoints_allow_human_review():
    result = assess_calibration_history(
        [
            benchmark_run("2026-06-01", 20),
            benchmark_run("2026-07-01", 27),
            benchmark_run("2026-08-01", 35),
        ]
    )

    assert result["schema"] == "calibration-history.v1"
    assert result["calibration_review_allowed"] is True
    assert result["automatic_threshold_changes_allowed"] is False
    assert result["latest_mature_observations"] == 35


def test_single_favorable_checkpoint_is_not_enough():
    result = assess_calibration_history([benchmark_run("2026-08-01", 40)])

    assert result["calibration_review_allowed"] is False
    assert "insufficient_calibration_checkpoints" in result["blockers"]


def test_repeated_scoring_same_outcomes_does_not_fake_stability():
    result = assess_calibration_history(
        [
            benchmark_run("2026-06-01", 30),
            benchmark_run("2026-07-01", 32),
            benchmark_run("2026-08-01", 33),
        ]
    )

    assert result["calibration_review_allowed"] is False
    assert "insufficient_new_mature_samples:2026-07-01" in result["blockers"]
    assert "insufficient_new_mature_samples:2026-08-01" in result["blockers"]


def test_latest_window_must_remain_safe():
    result = assess_calibration_history(
        [
            benchmark_run("2026-06-01", 20),
            benchmark_run("2026-07-01", 28, mae=-0.01),
            benchmark_run("2026-08-01", 36),
        ]
    )

    assert result["calibration_review_allowed"] is False
    assert "unsafe_checkpoint:2026-07-01" in result["blockers"]


def test_non_chronological_history_fails_closed():
    result = assess_calibration_history(
        [
            benchmark_run("2026-06-01", 20),
            benchmark_run("2026-08-01", 28),
            benchmark_run("2026-07-01", 36),
        ]
    )

    assert result["calibration_review_allowed"] is False
    assert "non_chronological_calibration_history" in result["blockers"]


def test_policy_requires_real_new_samples():
    policy = CalibrationSafetyPolicy(
        min_history_checkpoints=2,
        min_new_mature_samples_per_checkpoint=10,
    )
    result = assess_calibration_history(
        [benchmark_run("2026-07-01", 20), benchmark_run("2026-08-01", 29)],
        policy=policy,
    )

    assert result["calibration_review_allowed"] is False
    assert "insufficient_new_mature_samples:2026-08-01" in result["blockers"]
