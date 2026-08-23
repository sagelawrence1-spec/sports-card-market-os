from datetime import date

from calibration_safety import assess_calibration_history


def benchmark_run(day: str, mature):
    return {
        "evaluated_at": day,
        "result": {
            "evaluation_date": day,
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
        },
    }


def test_fractional_mature_counts_fail_closed_instead_of_truncating():
    result = assess_calibration_history(
        [
            benchmark_run("2026-06-01", 20),
            benchmark_run("2026-07-01", 27.9),
            benchmark_run("2026-08-01", 35),
        ],
        as_of=date(2026, 8, 23),
    )

    assert result["calibration_review_allowed"] is False
    assert "invalid_mature_observations:1" in result["blockers"]
    assert result["checkpoints_seen"] == 2


def test_boolean_mature_counts_fail_closed():
    result = assess_calibration_history(
        [
            benchmark_run("2026-06-01", 20),
            benchmark_run("2026-07-01", True),
            benchmark_run("2026-08-01", 35),
        ],
        as_of=date(2026, 8, 23),
    )

    assert result["calibration_review_allowed"] is False
    assert "invalid_mature_observations:1" in result["blockers"]


def test_integer_strings_remain_backward_compatible():
    result = assess_calibration_history(
        [
            benchmark_run("2026-06-01", "20"),
            benchmark_run("2026-07-01", "27"),
            benchmark_run("2026-08-01", "35"),
        ],
        as_of=date(2026, 8, 23),
    )

    assert result["calibration_review_allowed"] is True
    assert result["latest_mature_observations"] == 35
