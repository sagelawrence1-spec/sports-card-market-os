from datetime import date

import pytest

from comparable_lift import ComparableBenchmarkObservation, evaluate_comparable_lift


def _row(card_id: str, *, family: str = "topps chrome") -> ComparableBenchmarkObservation:
    return ComparableBenchmarkObservation(
        card_id=card_id,
        family=family,
        as_of_date=date(2026, 1, 1),
        horizon_days=30,
        current_price=100.0,
        baseline_estimate=120.0,
        comparable_estimate=108.0,
        realized_price=110.0,
        realized_at=date(2026, 2, 1),
    )


def test_exact_duplicate_decision_fails_closed() -> None:
    row = _row("card-1")
    with pytest.raises(ValueError, match="duplicate comparable benchmark decision"):
        evaluate_comparable_lift([row, row], evaluation_date=date(2026, 3, 1))


def test_normalized_card_identity_cannot_evade_duplicate_gate() -> None:
    first = _row("CARD-1")
    second = _row(" card-1 ", family="bowman chrome")
    with pytest.raises(ValueError, match="duplicate comparable benchmark decision"):
        evaluate_comparable_lift([first, second], evaluation_date=date(2026, 3, 1))


def test_same_card_can_have_distinct_decisions_at_distinct_as_of_dates() -> None:
    first = _row("card-1")
    second = ComparableBenchmarkObservation(
        **{**first.__dict__, "as_of_date": date(2026, 1, 2), "realized_at": date(2026, 2, 2)}
    )
    result = evaluate_comparable_lift(
        [first, second],
        evaluation_date=date(2026, 3, 1),
    )
    assert result["total_observations"] == 2
