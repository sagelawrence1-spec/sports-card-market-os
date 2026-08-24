from datetime import date

import pytest

from benchmark_outcome_integrity import assess_benchmark_outcome_integrity
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


def test_partial_outcome_price_without_date_fails_closed():
    result = assess_benchmark_outcome_integrity(
        [row(card_id="partial", realized=125.0, realized_at=None)],
        evaluation_date=date(2026, 2, 15),
    )

    assert result.partial_outcome_card_ids == ("partial",)
    assert "partial_realized_outcome_provenance" in result.blockers
    assert result.production_safe is False


def test_partial_outcome_date_without_price_fails_closed():
    result = assess_benchmark_outcome_integrity(
        [row(card_id="partial", realized=None, realized_at=date(2026, 2, 1))],
        evaluation_date=date(2026, 2, 15),
    )

    assert result.partial_outcome_card_ids == ("partial",)
    assert result.production_safe is False


def test_realized_outcome_before_horizon_fails_closed():
    result = assess_benchmark_outcome_integrity(
        [row(card_id="early", realized_at=date(2026, 1, 15))],
        evaluation_date=date(2026, 2, 15),
    )

    assert result.early_outcome_card_ids == ("early",)
    assert "realized_outcome_before_horizon" in result.blockers
    assert result.production_safe is False


def test_overdue_unsettled_outcome_is_not_merely_immature():
    result = assess_benchmark_outcome_integrity(
        [row(card_id="overdue", realized=None, realized_at=None)],
        evaluation_date=date(2026, 2, 15),
    )

    assert result.overdue_unsettled_card_ids == ("overdue",)
    assert "overdue_unsettled_forward_outcomes" in result.blockers
    assert result.production_safe is False


def test_future_horizon_without_outcome_remains_legitimately_immature():
    result = assess_benchmark_outcome_integrity(
        [
            row(
                card_id="future",
                as_of=date(2026, 2, 1),
                horizon=60,
                realized=None,
                realized_at=None,
            )
        ],
        evaluation_date=date(2026, 2, 15),
    )

    assert result.blockers == ()
    assert result.production_safe is True


def test_valid_mature_outcome_is_safe():
    result = assess_benchmark_outcome_integrity(
        [row(card_id="valid")], evaluation_date=date(2026, 2, 15)
    )

    assert result.blockers == ()
    assert result.production_safe is True


def test_blank_card_identity_fails_closed():
    with pytest.raises(ValueError, match="non-blank card_id"):
        assess_benchmark_outcome_integrity(
            [row(card_id="   ")], evaluation_date=date(2026, 2, 15)
        )


@pytest.mark.parametrize("card_id", [None, True, 7, 3.14])
def test_non_text_card_identity_fails_closed(card_id):
    with pytest.raises(ValueError, match="card_id to be text"):
        assess_benchmark_outcome_integrity(
            [row(card_id=card_id)], evaluation_date=date(2026, 2, 15)
        )


def test_card_identity_whitespace_is_canonicalized():
    result = assess_benchmark_outcome_integrity(
        [row(card_id="  valid-card  ")], evaluation_date=date(2026, 2, 15)
    )

    assert result.blockers == ()
    assert result.production_safe is True
