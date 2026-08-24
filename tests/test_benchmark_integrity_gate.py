from datetime import date

from benchmark_integrity_gate import evaluate_benchmark_with_integrity
from intelligence_benchmark import BenchmarkObservation


def row(
    *,
    card_id="card-1",
    as_of=date(2026, 1, 1),
    horizon=30,
    realized=125.0,
    realized_at=date(2026, 2, 1),
):
    return BenchmarkObservation(
        card_id=card_id,
        as_of_date=as_of,
        horizon_days=horizon,
        current_price=100.0,
        baseline_estimate=110.0,
        intelligence_estimate=120.0,
        realized_price=realized,
        realized_at=realized_at,
    )


def test_overdue_unsettled_outcome_blocks_ready_benchmark():
    result = evaluate_benchmark_with_integrity(
        [row(card_id="overdue", realized=None, realized_at=None)],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=0,
    )

    assert result["production_ready"] is False
    assert "overdue_unsettled_forward_outcomes" in result["blockers"]
    assert result["outcome_integrity"]["overdue_unsettled_card_ids"] == ["overdue"]


def test_partial_outcome_blocks_ready_benchmark():
    result = evaluate_benchmark_with_integrity(
        [row(card_id="partial", realized=125.0, realized_at=None)],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=0,
    )

    assert result["production_ready"] is False
    assert "partial_realized_outcome_provenance" in result["blockers"]


def test_early_outcome_blocks_ready_benchmark():
    result = evaluate_benchmark_with_integrity(
        [row(card_id="early", realized_at=date(2026, 1, 15))],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=0,
    )

    assert result["production_ready"] is False
    assert "realized_outcome_before_horizon" in result["blockers"]


def test_valid_mature_packet_can_remain_ready():
    result = evaluate_benchmark_with_integrity(
        [row(card_id="valid")],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=1,
    )

    assert result["production_ready"] is True
    assert result["blockers"] == []
    assert result["outcome_integrity"] == {
        "partial_outcome_card_ids": [],
        "early_outcome_card_ids": [],
        "overdue_unsettled_card_ids": [],
    }
