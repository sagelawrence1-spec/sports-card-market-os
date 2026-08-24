from datetime import date

from benchmark_integrity_gate import evaluate_benchmark_with_integrity
from intelligence_benchmark import BenchmarkObservation


def _mature_row() -> BenchmarkObservation:
    return BenchmarkObservation(
        card_id="card-1",
        as_of_date=date(2026, 1, 1),
        horizon_days=30,
        current_price=100.0,
        baseline_estimate=110.0,
        intelligence_estimate=120.0,
        realized_price=125.0,
        realized_at=date(2026, 2, 1),
    )


def test_negative_sample_gate_fails_closed_instead_of_weakening_readiness():
    result = evaluate_benchmark_with_integrity(
        [_mature_row()],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=-1,
    )

    assert result["production_ready"] is False
    assert "invalid_benchmark_min_mature_samples" in result["blockers"]
    assert result["min_mature_samples"] == 20


def test_boolean_sample_gate_fails_closed():
    result = evaluate_benchmark_with_integrity(
        [_mature_row()],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=True,
    )

    assert result["production_ready"] is False
    assert "invalid_benchmark_min_mature_samples" in result["blockers"]


def test_zero_sample_gate_remains_valid_for_explicit_test_replays():
    result = evaluate_benchmark_with_integrity(
        [_mature_row()],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=0,
    )

    assert "invalid_benchmark_min_mature_samples" not in result["blockers"]
    assert result["production_ready"] is True
