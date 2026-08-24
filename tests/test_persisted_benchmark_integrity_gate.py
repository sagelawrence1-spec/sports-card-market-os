from datetime import date

from intelligence_benchmark import BenchmarkObservation, IntelligenceBenchmarkStore


def _observation(*, realized_price=None, realized_at=None):
    return BenchmarkObservation(
        card_id="card-1",
        as_of_date=date(2026, 1, 1),
        horizon_days=30,
        current_price=100.0,
        baseline_estimate=105.0,
        intelligence_estimate=110.0,
        realized_price=realized_price,
        realized_at=realized_at,
        evidence_grade="A",
        confidence=0.9,
    )


def test_persisted_evaluation_blocks_overdue_unsettled_outcome(tmp_path):
    store = IntelligenceBenchmarkStore(tmp_path / "benchmark.sqlite")
    store.upsert_observation(_observation())

    result = store.evaluate_and_record(
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=0,
    )

    assert result["production_ready"] is False
    assert "overdue_unsettled_forward_outcomes" in result["blockers"]
    assert result["outcome_integrity"]["overdue_unsettled_card_ids"] == ["card-1"]

    persisted = store.load_runs()
    assert persisted[0]["result"]["production_ready"] is False
    assert persisted[0]["result"]["outcome_integrity"]["overdue_unsettled_card_ids"] == ["card-1"]


def test_persisted_evaluation_allows_valid_mature_outcome(tmp_path):
    store = IntelligenceBenchmarkStore(tmp_path / "benchmark.sqlite")
    store.upsert_observation(
        _observation(realized_price=112.0, realized_at=date(2026, 2, 1))
    )

    result = store.evaluate_and_record(
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=1,
    )

    assert result["production_ready"] is True
    assert result["blockers"] == []
    assert result["outcome_integrity"]["overdue_unsettled_card_ids"] == []
    assert store.load_runs()[0]["result"]["production_ready"] is True
