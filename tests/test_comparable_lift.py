from datetime import date

import pytest

from comparable_lift import (
    ComparableBenchmarkObservation,
    ComparableLiftPolicy,
    evaluate_comparable_lift,
)


def _row(
    index: int,
    *,
    family: str = "topps chrome",
    baseline: float = 120.0,
    comparable: float = 108.0,
    realized: float = 110.0,
    current: float = 100.0,
    as_of: date = date(2026, 1, 1),
    realized_at: date = date(2026, 2, 1),
) -> ComparableBenchmarkObservation:
    return ComparableBenchmarkObservation(
        card_id=f"card-{index}",
        family=family,
        as_of_date=as_of,
        horizon_days=30,
        current_price=current,
        baseline_estimate=baseline,
        comparable_estimate=comparable,
        realized_price=realized,
        realized_at=realized_at,
    )


def test_clean_comparable_lift_can_pass() -> None:
    rows = [_row(i, family="topps chrome" if i < 10 else "bowman chrome") for i in range(20)]
    result = evaluate_comparable_lift(rows, evaluation_date=date(2026, 3, 1))
    assert result["production_ready"] is True
    assert result["blockers"] == []
    assert result["overall"]["mae_improvement_pct"] > 0.05
    assert set(result["families"]) == {"bowman chrome", "topps chrome"}


def test_immature_future_outcomes_do_not_enter_metrics() -> None:
    mature = [_row(i) for i in range(20)]
    future = _row(
        21,
        as_of=date(2026, 2, 15),
        realized_at=date(2026, 4, 1),
        baseline=500.0,
        comparable=1.0,
        realized=1.0,
    )
    result = evaluate_comparable_lift(
        [*mature, future], evaluation_date=date(2026, 3, 1)
    )
    assert result["mature_observations"] == 20
    assert result["immature_observations"] == 1
    assert result["overall"]["observations"] == 20


def test_under_sampled_family_blocks_aggregate_win() -> None:
    rows = [_row(i, family="topps chrome") for i in range(19)]
    rows.append(_row(20, family="rare family"))
    result = evaluate_comparable_lift(rows, evaluation_date=date(2026, 3, 1))
    assert result["production_ready"] is False
    assert "insufficient_family_samples" in result["blockers"]
    assert result["thin_families"] == ["rare family"]


def test_family_mae_regression_blocks_aggregate_win() -> None:
    rows = [_row(i, family="topps chrome") for i in range(15)]
    rows.extend(
        _row(i, family="bowman chrome", comparable=130.0)
        for i in range(15, 20)
    )
    result = evaluate_comparable_lift(rows, evaluation_date=date(2026, 3, 1))
    assert result["overall"]["mae_improvement_pct"] > 0.05
    assert result["production_ready"] is False
    assert "family_mae_regression" in result["blockers"]
    assert result["mae_regressing_families"] == ["bowman chrome"]


def test_family_directional_regression_blocks_aggregate_win() -> None:
    rows = [
        _row(i, family="topps chrome", baseline=90.0, comparable=108.0)
        for i in range(15)
    ]
    rows.extend(
        _row(i, family="bowman chrome", comparable=90.0, baseline=130.0)
        for i in range(15, 20)
    )
    result = evaluate_comparable_lift(
        rows,
        evaluation_date=date(2026, 3, 1),
        policy=ComparableLiftPolicy(
            min_mae_improvement_pct=-1.0,
            min_family_mae_improvement_pct=-1.0,
        ),
    )
    assert result["overall"]["directional_lift"] >= 0.0
    assert result["production_ready"] is False
    assert "family_directional_regression" in result["blockers"]
    assert result["directional_regressing_families"] == ["bowman chrome"]


def test_mae_regression_blocks_release() -> None:
    rows = [_row(i, baseline=108.0, comparable=130.0, realized=110.0) for i in range(20)]
    result = evaluate_comparable_lift(rows, evaluation_date=date(2026, 3, 1))
    assert result["production_ready"] is False
    assert "insufficient_mae_lift" in result["blockers"]


def test_directional_regression_blocks_release() -> None:
    rows = [
        _row(i, baseline=120.0, comparable=90.0, realized=110.0, current=100.0)
        for i in range(20)
    ]
    result = evaluate_comparable_lift(
        rows,
        evaluation_date=date(2026, 3, 1),
        policy=ComparableLiftPolicy(
            min_mae_improvement_pct=-1.0,
            min_family_mae_improvement_pct=-1.0,
        ),
    )
    assert result["production_ready"] is False
    assert "directional_accuracy_regression" in result["blockers"]


def test_net_realized_price_includes_fees_and_liquidity() -> None:
    row = ComparableBenchmarkObservation(
        card_id="fees",
        family="topps chrome",
        as_of_date=date(2026, 1, 1),
        horizon_days=30,
        current_price=80.0,
        baseline_estimate=90.0,
        comparable_estimate=85.0,
        realized_price=100.0,
        realized_at=date(2026, 2, 1),
        exit_fee_rate=0.10,
        liquidity_haircut_rate=0.10,
    )
    assert row.net_realized_price == pytest.approx(81.0)


def test_missing_family_fails_closed_for_mature_observation() -> None:
    rows = [_row(i) for i in range(19)] + [_row(20, family="")]
    with pytest.raises(ValueError, match="family is required"):
        evaluate_comparable_lift(rows, evaluation_date=date(2026, 3, 1))


def test_policy_validation_fails_closed() -> None:
    with pytest.raises(ValueError, match="min_mature_samples"):
        ComparableLiftPolicy(min_mature_samples=0).validate()
    with pytest.raises(ValueError, match="min_family_samples"):
        ComparableLiftPolicy(min_family_samples=0).validate()
    with pytest.raises(ValueError, match="min_family_mae_improvement_pct"):
        ComparableLiftPolicy(min_family_mae_improvement_pct=1.1).validate()
    with pytest.raises(ValueError, match="min_family_directional_lift"):
        ComparableLiftPolicy(min_family_directional_lift=-1.1).validate()
