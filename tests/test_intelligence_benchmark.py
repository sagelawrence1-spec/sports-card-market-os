from datetime import date

from intelligence_benchmark import BenchmarkObservation, evaluate_intelligence_vs_baseline


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
    )


def test_immature_forward_rows_do_not_enter_metrics():
    mature = obs(card_id="mature")
    immature = obs(card_id="immature", realized_at=date(2026, 1, 15), realized=1000.0)

    result = evaluate_intelligence_vs_baseline([mature, immature], min_mature_samples=1)

    assert result["mature_observations"] == 1
    assert result["immature_observations"] == 1
    assert result["baseline"]["mae"] == 15.0
    assert result["intelligence"]["mae"] == 5.0


def test_missing_realized_outcome_is_immature():
    row = obs(realized=None, realized_at=None)
    result = evaluate_intelligence_vs_baseline([row], min_mature_samples=1)

    assert result["mature_observations"] == 0
    assert result["baseline"]["mae"] is None
    assert result["intelligence"]["directional_accuracy"] is None
    assert result["production_ready"] is False


def test_reports_error_lift_against_simple_baseline():
    rows = [
        obs(card_id="a", baseline=120.0, intelligence=128.0, realized=130.0),
        obs(card_id="b", current=200.0, baseline=210.0, intelligence=190.0, realized=185.0),
    ]
    result = evaluate_intelligence_vs_baseline(rows, min_mature_samples=2)

    assert result["baseline"]["mae"] == 17.5
    assert result["intelligence"]["mae"] == 3.5
    assert result["lift"]["mae_improvement_pct"] > 0.79
    assert result["production_ready"] is True


def test_directional_accuracy_compares_forecast_to_as_of_price():
    rows = [
        obs(card_id="up", current=100.0, baseline=90.0, intelligence=120.0, realized=130.0),
        obs(card_id="down", current=100.0, baseline=110.0, intelligence=80.0, realized=70.0),
    ]
    result = evaluate_intelligence_vs_baseline(rows, min_mature_samples=2)

    assert result["baseline"]["directional_accuracy"] == 0.0
    assert result["intelligence"]["directional_accuracy"] == 1.0
    assert result["lift"]["directional_accuracy_lift"] == 1.0


def test_small_samples_cannot_unlock_production_readiness():
    rows = [obs(card_id=f"card-{idx}") for idx in range(3)]
    result = evaluate_intelligence_vs_baseline(rows, min_mature_samples=20)

    assert result["production_ready"] is False
    assert "insufficient_mature_forward_samples" in result["blockers"]
