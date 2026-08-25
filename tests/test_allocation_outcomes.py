import pytest

from allocation_audit import AllocationDecision
from allocation_outcomes import (
    AllocationOutcome,
    AllocationOutcomePolicy,
    grade_allocation,
    grade_allocation_journal,
)


def decision(*, run_id="run-1", card_id="card-a", approved=1000.0, ready=True):
    return AllocationDecision(
        run_id=run_id,
        card_id=card_id,
        decided_at="2026-08-01T12:00:00+00:00",
        requested_allocation=1200.0,
        approved_allocation=approved,
        ready=ready,
        blockers=(),
        exposure_blockers=(),
        evidence_grade="A",
        confidence=0.91,
        action="BUY",
        details={"upside": 0.25},
    )


def test_grades_realized_return_against_deployed_capital():
    row = grade_allocation(
        decision(),
        AllocationOutcome("run-1", "card-a", "2026-09-01T12:00:00+00:00", 1250.0),
    )
    assert row["realized_return"] == pytest.approx(0.25)
    assert row["pnl"] == pytest.approx(250.0)
    assert row["grade"] == "A"
    assert row["hit"] is True


def test_exit_fees_are_applied_before_grading():
    row = grade_allocation(
        decision(),
        AllocationOutcome("run-1", "card-a", "2026-09-01T12:00:00+00:00", 1100.0),
        policy=AllocationOutcomePolicy(exit_fee_rate=0.10),
    )
    assert row["net_realized_proceeds"] == pytest.approx(990.0)
    assert row["realized_return"] == pytest.approx(-0.01)
    assert row["grade"] == "D"
    assert row["hit"] is False


def test_blocked_or_zero_allocation_cannot_be_graded():
    outcome = AllocationOutcome("run-1", "card-a", "2026-09-01T12:00:00+00:00", 900.0)
    with pytest.raises(ValueError, match="deployed"):
        grade_allocation(decision(ready=False), outcome)
    with pytest.raises(ValueError, match="deployed"):
        grade_allocation(decision(approved=0), outcome)


def test_outcome_cannot_precede_decision():
    with pytest.raises(ValueError, match="predates"):
        grade_allocation(
            decision(),
            AllocationOutcome("run-1", "card-a", "2026-07-31T12:00:00+00:00", 1000.0),
        )


def test_journal_reports_settled_and_unsettled_allocations():
    decisions = [
        decision(card_id="a", approved=1000),
        decision(card_id="b", approved=500),
        decision(card_id="blocked", approved=0, ready=False),
    ]
    packet = grade_allocation_journal(
        decisions,
        [AllocationOutcome("run-1", "a", "2026-09-01T12:00:00+00:00", 1200.0)],
    )
    assert packet["eligible_allocations"] == 2
    assert packet["graded_allocations"] == 1
    assert packet["unsettled_allocations"] == 1
    assert packet["deployed_capital"] == pytest.approx(1000.0)
    assert packet["realized_pnl"] == pytest.approx(200.0)
    assert packet["portfolio_return"] == pytest.approx(0.20)
    assert packet["hit_rate"] == 1.0
    assert len(packet["packet_sha256"]) == 64


def test_duplicate_decisions_or_outcomes_fail_closed():
    d = decision()
    o = AllocationOutcome("run-1", "card-a", "2026-09-01T12:00:00+00:00", 1100.0)
    with pytest.raises(ValueError, match="duplicate allocation decision"):
        grade_allocation_journal([d, d], [o])
    with pytest.raises(ValueError, match="duplicate allocation outcome"):
        grade_allocation_journal([d], [o, o])


def test_orphan_outcome_fails_closed():
    with pytest.raises(ValueError, match="orphan"):
        grade_allocation_journal(
            [decision()],
            [AllocationOutcome("run-2", "card-b", "2026-09-01T12:00:00+00:00", 1100.0)],
        )


def test_invalid_outcome_and_policy_values_fail_closed():
    with pytest.raises(ValueError, match="realized_proceeds"):
        grade_allocation(
            decision(),
            AllocationOutcome("run-1", "card-a", "2026-09-01T12:00:00+00:00", float("nan")),
        )
    with pytest.raises(ValueError, match="exit_fee_rate"):
        grade_allocation(
            decision(),
            AllocationOutcome("run-1", "card-a", "2026-09-01T12:00:00+00:00", 1000.0),
            policy=AllocationOutcomePolicy(exit_fee_rate=1.1),
        )
