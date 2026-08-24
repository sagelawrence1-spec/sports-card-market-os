from datetime import date

from benchmark_integrity_gate import evaluate_benchmark_with_integrity
from intelligence_benchmark import BenchmarkObservation


def valid_row(card_id: str = "valid") -> BenchmarkObservation:
    return BenchmarkObservation(
        card_id=card_id,
        as_of_date=date(2026, 1, 1),
        horizon_days=30,
        current_price=100.0,
        baseline_estimate=110.0,
        intelligence_estimate=120.0,
        realized_price=125.0,
        realized_at=date(2026, 2, 1),
        confidence=0.8,
        exit_fee_rate=0.0,
        liquidity_haircut_rate=0.0,
    )


def test_null_observation_container_fails_closed_instead_of_raising():
    result = evaluate_benchmark_with_integrity(
        None,
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=0,
    )

    assert result["production_ready"] is False
    assert "invalid_benchmark_observation_container" in result["blockers"]
    assert result["total_observations"] == 0


def test_mapping_and_text_containers_fail_closed_instead_of_iterating_members():
    for observations in ({"card_id": "bad"}, "not-a-benchmark-packet"):
        result = evaluate_benchmark_with_integrity(
            observations,
            evaluation_date=date(2026, 2, 15),
            min_mature_samples=0,
        )

        assert result["production_ready"] is False
        assert "invalid_benchmark_observation_container" in result["blockers"]
        assert result["mature_observations"] == 0


def test_invalid_observation_member_is_excluded_and_blocks_readiness():
    result = evaluate_benchmark_with_integrity(
        [valid_row(), {"card_id": "spoof"}],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=1,
    )

    assert result["production_ready"] is False
    assert "invalid_benchmark_observation_member" in result["blockers"]
    assert result["mature_observations"] == 1
    assert result["total_observations"] == 2
    assert result["outcome_integrity"]["invalid_observation_members"] == 1


def test_generator_of_valid_observations_remains_supported():
    result = evaluate_benchmark_with_integrity(
        (row for row in [valid_row()]),
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=1,
    )

    assert result["production_ready"] is True
    assert result["mature_observations"] == 1
    assert "invalid_benchmark_observation_container" not in result["blockers"]
    assert "invalid_benchmark_observation_member" not in result["blockers"]
