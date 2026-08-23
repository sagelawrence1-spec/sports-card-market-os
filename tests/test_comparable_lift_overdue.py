from datetime import date

from comparable_lift import ComparableBenchmarkObservation, evaluate_comparable_lift


def _row(index: int, *, realized_price=110.0, realized_at=date(2026, 2, 1)):
    return ComparableBenchmarkObservation(
        card_id=f"card-{index}",
        family="topps chrome",
        as_of_date=date(2026, 1, 1),
        horizon_days=30,
        current_price=100.0,
        baseline_estimate=120.0,
        comparable_estimate=108.0,
        realized_price=realized_price,
        realized_at=realized_at,
    )


def test_overdue_unsettled_outcome_blocks_release() -> None:
    rows = [_row(i) for i in range(20)]
    rows.append(_row(99, realized_price=None, realized_at=None))
    result = evaluate_comparable_lift(rows, evaluation_date=date(2026, 3, 1))
    assert result["production_ready"] is False
    assert "overdue_unsettled_outcomes" in result["blockers"]
    assert result["overdue_unsettled_observations"] == 1
    assert result["overdue_unsettled_card_ids"] == ["card-99"]


def test_future_unsettled_outcome_is_not_overdue() -> None:
    future = ComparableBenchmarkObservation(
        card_id="future-card",
        family="topps chrome",
        as_of_date=date(2026, 2, 15),
        horizon_days=30,
        current_price=100.0,
        baseline_estimate=120.0,
        comparable_estimate=108.0,
    )
    result = evaluate_comparable_lift(
        [*[_row(i) for i in range(20)], future],
        evaluation_date=date(2026, 3, 1),
    )
    assert "overdue_unsettled_outcomes" not in result["blockers"]
    assert result["overdue_unsettled_observations"] == 0
