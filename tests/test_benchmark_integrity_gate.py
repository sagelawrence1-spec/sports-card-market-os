from datetime import date, datetime

from benchmark_integrity_gate import evaluate_benchmark_with_integrity
from intelligence_benchmark import BenchmarkObservation


def row(
    *,
    card_id="card-1",
    as_of=date(2026, 1, 1),
    horizon=30,
    current_price=100.0,
    baseline_estimate=110.0,
    intelligence_estimate=120.0,
    realized=125.0,
    realized_at=date(2026, 2, 1),
    confidence=None,
    exit_fee_rate=0.0,
    liquidity_haircut_rate=0.0,
):
    return BenchmarkObservation(
        card_id=card_id,
        as_of_date=as_of,
        horizon_days=horizon,
        current_price=current_price,
        baseline_estimate=baseline_estimate,
        intelligence_estimate=intelligence_estimate,
        realized_price=realized,
        realized_at=realized_at,
        confidence=confidence,
        exit_fee_rate=exit_fee_rate,
        liquidity_haircut_rate=liquidity_haircut_rate,
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


def test_invalid_outcome_is_blocked_before_scoring_math():
    result = evaluate_benchmark_with_integrity(
        [row(card_id="invalid", realized=float("nan"))],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=0,
    )

    assert result["production_ready"] is False
    assert "invalid_realized_outcome_provenance" in result["blockers"]
    assert result["outcome_integrity"]["invalid_outcome_card_ids"] == ["invalid"]
    assert result["mature_observations"] == 0
    assert result["total_observations"] == 1


def test_duplicate_decision_packets_fail_closed_and_do_not_inflate_scoring():
    result = evaluate_benchmark_with_integrity(
        [row(card_id="dup"), row(card_id=" dup ")],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=0,
    )

    assert result["production_ready"] is False
    assert "duplicate_benchmark_decision_packet" in result["blockers"]
    assert result["outcome_integrity"]["duplicate_decision_card_ids"] == ["dup"]
    assert result["total_observations"] == 2
    assert result["mature_observations"] == 0


def test_future_decision_is_blocked_and_excluded_from_scoring():
    result = evaluate_benchmark_with_integrity(
        [
            row(
                card_id="future-decision",
                as_of=date(2026, 3, 1),
                realized=None,
                realized_at=None,
            )
        ],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=0,
    )

    assert result["production_ready"] is False
    assert "benchmark_decision_after_evaluation_cutoff" in result["blockers"]
    assert result["outcome_integrity"]["future_decision_card_ids"] == ["future-decision"]
    assert result["total_observations"] == 1
    assert result["mature_observations"] == 0
    assert result["immature_observations"] == 0


def test_malformed_decision_date_fails_closed_before_date_comparison():
    result = evaluate_benchmark_with_integrity(
        [row(card_id="bad-date", as_of=datetime(2026, 1, 1, 12, 0))],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=0,
    )

    assert result["production_ready"] is False
    assert "invalid_benchmark_decision_provenance" in result["blockers"]
    assert result["outcome_integrity"]["invalid_decision_card_ids"] == ["bad-date"]
    assert result["mature_observations"] == 0


def test_non_positive_or_boolean_horizon_fails_closed_before_scoring():
    result = evaluate_benchmark_with_integrity(
        [row(card_id="zero", horizon=0), row(card_id="boolean", horizon=True)],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=0,
    )

    assert result["production_ready"] is False
    assert "invalid_benchmark_decision_provenance" in result["blockers"]
    assert result["outcome_integrity"]["invalid_decision_card_ids"] == ["boolean", "zero"]
    assert result["mature_observations"] == 0


def test_non_text_card_identity_fails_closed_before_outcome_integrity():
    result = evaluate_benchmark_with_integrity(
        [row(card_id=7)],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=0,
    )

    assert result["production_ready"] is False
    assert "invalid_benchmark_decision_provenance" in result["blockers"]
    assert result["outcome_integrity"]["invalid_decision_card_ids"] == ["<invalid-card-id>"]
    assert result["mature_observations"] == 0


def test_non_finite_or_non_positive_decision_prices_fail_closed_before_scoring():
    result = evaluate_benchmark_with_integrity(
        [
            row(card_id="nan-current", current_price=float("nan")),
            row(card_id="inf-baseline", baseline_estimate=float("inf")),
            row(card_id="zero-intelligence", intelligence_estimate=0.0),
        ],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=0,
    )

    assert result["production_ready"] is False
    assert "invalid_benchmark_decision_values" in result["blockers"]
    assert result["outcome_integrity"]["invalid_decision_value_card_ids"] == [
        "inf-baseline",
        "nan-current",
        "zero-intelligence",
    ]
    assert result["mature_observations"] == 0


def test_invalid_confidence_and_cost_rates_fail_closed_before_scoring():
    result = evaluate_benchmark_with_integrity(
        [
            row(card_id="bad-confidence", confidence=1.1),
            row(card_id="bad-fee", exit_fee_rate=-0.01),
            row(card_id="bad-haircut", liquidity_haircut_rate=float("nan")),
        ],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=0,
    )

    assert result["production_ready"] is False
    assert "invalid_benchmark_decision_values" in result["blockers"]
    assert result["outcome_integrity"]["invalid_decision_value_card_ids"] == [
        "bad-confidence",
        "bad-fee",
        "bad-haircut",
    ]
    assert result["mature_observations"] == 0


def test_valid_boundary_confidence_and_cost_rates_remain_eligible():
    result = evaluate_benchmark_with_integrity(
        [row(card_id="valid-boundaries", confidence=1.0, exit_fee_rate=0.0, liquidity_haircut_rate=1.0)],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=1,
    )

    assert result["production_ready"] is True
    assert "invalid_benchmark_decision_values" not in result["blockers"]
    assert result["mature_observations"] == 1


def test_decision_on_evaluation_cutoff_remains_eligible():
    result = evaluate_benchmark_with_integrity(
        [
            row(
                card_id="same-day",
                as_of=date(2026, 2, 15),
                realized=None,
                realized_at=None,
            )
        ],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=0,
    )

    assert result["production_ready"] is True
    assert "benchmark_decision_after_evaluation_cutoff" not in result["blockers"]
    assert result["outcome_integrity"]["future_decision_card_ids"] == []
    assert result["immature_observations"] == 1


def test_same_card_distinct_horizons_remain_independent_decisions():
    result = evaluate_benchmark_with_integrity(
        [
            row(card_id="card-1", horizon=30, realized_at=date(2026, 2, 1)),
            row(card_id="card-1", horizon=45, realized_at=date(2026, 2, 20)),
        ],
        evaluation_date=date(2026, 2, 20),
        min_mature_samples=2,
    )

    assert result["production_ready"] is True
    assert "duplicate_benchmark_decision_packet" not in result["blockers"]
    assert result["mature_observations"] == 2


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
        "invalid_outcome_card_ids": [],
        "invalid_decision_card_ids": [],
        "invalid_decision_value_card_ids": [],
        "duplicate_decision_card_ids": [],
        "future_decision_card_ids": [],
    }


def test_malformed_evaluation_cutoff_fails_closed_instead_of_raising():
    result = evaluate_benchmark_with_integrity(
        [row(card_id="bad-cutoff")],
        evaluation_date=datetime(2026, 2, 15, 12, 0),
        min_mature_samples=0,
    )

    assert result["production_ready"] is False
    assert "invalid_benchmark_evaluation_date" in result["blockers"]
    assert result["outcome_integrity"]["invalid_evaluation_date"] is True


def test_valid_date_cutoff_does_not_emit_cutoff_integrity_blocker():
    result = evaluate_benchmark_with_integrity(
        [row(card_id="valid-cutoff")],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=1,
    )

    assert "invalid_benchmark_evaluation_date" not in result["blockers"]
    assert "invalid_evaluation_date" not in result["outcome_integrity"]
