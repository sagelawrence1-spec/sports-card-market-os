from datetime import date

from intelligence_benchmark import (
    BenchmarkObservation,
    IntelligenceBenchmarkStore,
    evaluate_intelligence_vs_baseline,
)


def obs(
    *,
    card_id="card-1",
    as_of=date(2026, 1, 1),
    horizon=30,
    current=100.0,
    baseline=110.0,
    intelligence=120.0,
    realized=125.0,
    realized_at=date(2026, 2, 1),
    evidence_grade="A",
    confidence=0.9,
):
    return BenchmarkObservation(
        card_id=card_id,
        as_of_date=as_of,
        horizon_days=horizon,
        current_price=current,
        baseline_estimate=baseline,
        intelligence_estimate=intelligence,
        realized_price=realized,
        realized_at=realized_at,
        evidence_grade=evidence_grade,
        confidence=confidence,
    )


def test_immature_forward_rows_do_not_enter_metrics():
    mature = obs(card_id="mature")
    immature = obs(card_id="immature", realized_at=date(2026, 1, 15), realized=1000.0)

    result = evaluate_intelligence_vs_baseline(
        [mature, immature], evaluation_date=date(2026, 2, 15), min_mature_samples=1
    )

    assert result["mature_observations"] == 1
    assert result["immature_observations"] == 1
    assert result["baseline"]["mae"] == 15.0
    assert result["intelligence"]["mae"] == 5.0


def test_future_realized_row_cannot_leak_into_historical_replay():
    future_outcome = obs(realized_at=date(2026, 3, 1), realized=500.0)

    result = evaluate_intelligence_vs_baseline(
        [future_outcome], evaluation_date=date(2026, 2, 15), min_mature_samples=1
    )

    assert result["mature_observations"] == 0
    assert result["production_ready"] is False


def test_reports_lift_against_simple_baseline():
    rows = [
        obs(card_id="a", baseline=120.0, intelligence=128.0, realized=130.0),
        obs(card_id="b", current=200.0, baseline=210.0, intelligence=190.0, realized=185.0),
    ]
    result = evaluate_intelligence_vs_baseline(
        rows, evaluation_date=date(2026, 2, 15), min_mature_samples=2
    )

    assert result["baseline"]["mae"] == 17.5
    assert result["intelligence"]["mae"] == 3.5
    assert result["lift"]["mae_improvement_pct"] > 0.79
    assert result["production_ready"] is True


def test_directional_accuracy_compares_forecast_to_as_of_price():
    rows = [
        obs(card_id="up", current=100.0, baseline=90.0, intelligence=120.0, realized=130.0),
        obs(card_id="down", current=100.0, baseline=110.0, intelligence=80.0, realized=70.0),
    ]
    result = evaluate_intelligence_vs_baseline(
        rows, evaluation_date=date(2026, 2, 15), min_mature_samples=2
    )

    assert result["baseline"]["directional_accuracy"] == 0.0
    assert result["intelligence"]["directional_accuracy"] == 1.0
    assert result["lift"]["directional_accuracy_lift"] == 1.0


def test_store_upsert_is_deterministic_and_survives_restart(tmp_path):
    db = tmp_path / "benchmark.sqlite"
    store = IntelligenceBenchmarkStore(db)
    store.upsert_observation(obs(intelligence=115.0))
    store.upsert_observation(obs(intelligence=121.0))

    restarted = IntelligenceBenchmarkStore(db)
    rows = restarted.load_observations()

    assert len(rows) == 1
    assert rows[0].intelligence_estimate == 121.0
    assert rows[0].evidence_grade == "A"
    assert rows[0].confidence == 0.9


def test_store_records_append_only_benchmark_runs(tmp_path):
    store = IntelligenceBenchmarkStore(tmp_path / "benchmark.sqlite")
    store.upsert_observation(obs())

    first = store.evaluate_and_record(
        evaluation_date=date(2026, 2, 15), min_mature_samples=1
    )
    second = store.evaluate_and_record(
        evaluation_date=date(2026, 2, 16), min_mature_samples=1
    )
    runs = store.load_runs()

    assert first["production_ready"] is True
    assert second["production_ready"] is True
    assert [run["evaluated_at"] for run in runs] == ["2026-02-15", "2026-02-16"]
    assert runs[0]["result"]["mature_observations"] == 1


def test_small_samples_cannot_unlock_production_readiness():
    rows = [obs(card_id=f"card-{idx}") for idx in range(3)]
    result = evaluate_intelligence_vs_baseline(
        rows, evaluation_date=date(2026, 2, 15), min_mature_samples=20
    )

    assert result["production_ready"] is False
    assert "insufficient_mature_forward_samples" in result["blockers"]
