from datetime import date

import pytest

from benchmark_cohort_performance import benchmark_cohort_performance
from benchmark_integrity_gate import evaluate_benchmark_with_integrity
from intelligence_benchmark import BenchmarkObservation


def obs(
    card_id: str,
    *,
    as_of: date,
    current: float = 100.0,
    baseline: float = 110.0,
    intelligence: float = 120.0,
    realized: float = 120.0,
    evidence_grade: str = "A",
    confidence: float | None = 0.8,
) -> BenchmarkObservation:
    return BenchmarkObservation(
        card_id=card_id,
        as_of_date=as_of,
        horizon_days=30,
        current_price=current,
        baseline_estimate=baseline,
        intelligence_estimate=intelligence,
        realized_price=realized,
        realized_at=date(2026, 3, 1),
        evidence_grade=evidence_grade,
        confidence=confidence,
    )


def test_reports_hit_rate_valuation_error_drawdown_and_calibration_by_cohort():
    rows = [
        obs("a", as_of=date(2026, 1, 1), intelligence=120.0, realized=120.0, confidence=0.9),
        obs("b", as_of=date(2026, 1, 2), intelligence=120.0, realized=90.0, confidence=0.8),
        obs(
            "c",
            as_of=date(2026, 1, 3),
            intelligence=120.0,
            realized=80.0,
            evidence_grade="B",
            confidence=0.7,
        ),
    ]

    result = benchmark_cohort_performance(rows, evaluation_date=date(2026, 3, 2))
    intelligence = result["overall"]["intelligence"]

    assert intelligence["hit_rate"] == pytest.approx(1 / 3)
    assert intelligence["valuation_error_mae_pct"] == pytest.approx(
        (0.0 + (30 / 90) + (40 / 80)) / 3
    )
    assert intelligence["max_drawdown_pct"] == pytest.approx(0.3)
    assert intelligence["calibration_error_mae"] == pytest.approx((0.1 + 0.8 + 0.7) / 3)

    grade_a = result["cohorts"]["evidence_grade"]["A"]
    grade_b = result["cohorts"]["evidence_grade"]["B"]
    assert grade_a["observations"] == 2
    assert grade_b["observations"] == 1
    assert grade_a["intelligence"]["hit_rate"] == pytest.approx(0.5)
    assert grade_b["intelligence"]["hit_rate"] == 0.0


def test_drawdown_replays_decisions_in_chronological_order_not_input_order():
    rows = [
        obs("c", as_of=date(2026, 1, 3), intelligence=120.0, realized=80.0),
        obs("a", as_of=date(2026, 1, 1), intelligence=120.0, realized=120.0),
        obs("b", as_of=date(2026, 1, 2), intelligence=120.0, realized=90.0),
    ]

    result = benchmark_cohort_performance(rows, evaluation_date=date(2026, 3, 2))

    assert result["overall"]["intelligence"]["max_drawdown_pct"] == pytest.approx(0.3)


def test_immature_rows_do_not_enter_cohort_performance():
    mature = obs("mature", as_of=date(2026, 1, 1))
    immature = BenchmarkObservation(
        card_id="immature",
        as_of_date=date(2026, 2, 20),
        horizon_days=30,
        current_price=100.0,
        baseline_estimate=110.0,
        intelligence_estimate=120.0,
        realized_price=None,
        realized_at=None,
        evidence_grade="A",
        confidence=0.9,
    )

    result = benchmark_cohort_performance(
        [mature, immature], evaluation_date=date(2026, 3, 2)
    )

    assert result["overall"]["observations"] == 1


def test_integrity_gated_result_persists_cohort_performance_output():
    rows = [
        obs("a", as_of=date(2026, 1, 1), intelligence=120.0, realized=120.0),
        obs("b", as_of=date(2026, 1, 2), intelligence=80.0, realized=80.0),
    ]

    result = evaluate_benchmark_with_integrity(
        rows,
        evaluation_date=date(2026, 3, 2),
        min_mature_samples=2,
    )

    assert result["production_ready"] is True
    performance = result["cohort_performance"]
    assert performance["overall"]["observations"] == 2
    assert performance["overall"]["intelligence"]["hit_rate"] == 1.0
    assert "valuation_error_mae_pct" in performance["overall"]["intelligence"]
    assert "max_drawdown_pct" in performance["overall"]["intelligence"]
    assert "calibration_error_mae" in performance["overall"]["intelligence"]
