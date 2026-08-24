from datetime import date

import pytest

from benchmark_integrity_gate import evaluate_benchmark_with_integrity
from intelligence_benchmark import BenchmarkObservation


def _row(*, card_id="card-1", evidence_grade="A"):
    return BenchmarkObservation(
        card_id=card_id,
        as_of_date=date(2026, 1, 1),
        horizon_days=30,
        current_price=100.0,
        baseline_estimate=105.0,
        intelligence_estimate=110.0,
        realized_price=112.0,
        realized_at=date(2026, 2, 1),
        evidence_grade=evidence_grade,
        confidence=0.9,
    )


@pytest.mark.parametrize("bad_grade", [True, 7, "", " A", "A "])
def test_malformed_evidence_grade_blocks_and_is_excluded(bad_grade):
    result = evaluate_benchmark_with_integrity(
        [_row(evidence_grade=bad_grade)],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=0,
    )

    assert result["production_ready"] is False
    assert "invalid_benchmark_evidence_grade" in result["blockers"]
    assert result["mature_observations"] == 0
    assert result["outcome_integrity"]["invalid_evidence_grade_card_ids"] == ["card-1"]


def test_missing_evidence_grade_remains_valid_unknown_segment():
    result = evaluate_benchmark_with_integrity(
        [_row(evidence_grade=None)],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=1,
    )

    assert result["production_ready"] is True
    assert result["blockers"] == []
    assert result["segments"]["evidence_grade"]["unknown"]["observations"] == 1


def test_valid_evidence_grade_remains_scoreable():
    result = evaluate_benchmark_with_integrity(
        [_row(evidence_grade="A")],
        evaluation_date=date(2026, 2, 15),
        min_mature_samples=1,
    )

    assert result["production_ready"] is True
    assert result["segments"]["evidence_grade"]["A"]["observations"] == 1
