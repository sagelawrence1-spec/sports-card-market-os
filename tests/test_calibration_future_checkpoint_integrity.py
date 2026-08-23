from datetime import date, timedelta

from calibration_safety import assess_calibration_history


def benchmark_run(day: str, mature: int) -> dict:
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


def test_future_checkpoint_cannot_manufacture_history() -> None:
    cutoff = date(2026, 8, 23)
    future_day = (cutoff + timedelta(days=1)).isoformat()

    result = assess_calibration_history(
        [
            benchmark_run("2026-06-01", 20),
            benchmark_run("2026-07-01", 27),
            benchmark_run(future_day, 35),
        ],
        as_of=cutoff,
    )

    assert result["calibration_review_allowed"] is False
    assert "future_evaluation_date:2" in result["blockers"]
    assert result["checkpoints_seen"] == 2
    assert result["latest_evaluation_date"] == "2026-07-01"


def test_checkpoint_on_as_of_date_remains_valid() -> None:
    cutoff = date(2026, 8, 23)

    result = assess_calibration_history(
        [
            benchmark_run("2026-06-01", 20),
            benchmark_run("2026-07-01", 27),
            benchmark_run(cutoff.isoformat(), 35),
        ],
        as_of=cutoff,
    )

    assert result["calibration_review_allowed"] is True
    assert result["latest_evaluation_date"] == cutoff.isoformat()


def test_default_cutoff_rejects_tomorrow() -> None:
    today = date.today()
    tomorrow = (today + timedelta(days=1)).isoformat()

    result = assess_calibration_history(
        [
            benchmark_run((today - timedelta(days=60)).isoformat(), 20),
            benchmark_run((today - timedelta(days=30)).isoformat(), 27),
            benchmark_run(tomorrow, 35),
        ]
    )

    assert result["calibration_review_allowed"] is False
    assert "future_evaluation_date:2" in result["blockers"]
