from datetime import date

import pytest

from recommendation_journal import Recommendation
from recommendation_outcomes import OutcomePolicy, grade_journal, grade_recommendation


def _rec(action="BUY", entry=100.0, realized=120.0, realized_at=date(2026, 2, 1)):
    return Recommendation(
        observation_id=f"obs-{action.lower()}",
        card_id="card-1",
        as_of_date=date(2026, 1, 1),
        action=action,
        entry_price=entry,
        fair_value=125.0,
        confidence=0.8,
        evidence_grade="A",
        thesis="test",
        horizon_days=30,
        realized_price=realized,
        realized_at=realized_at,
    )


def test_buy_rewards_positive_net_return():
    result = grade_recommendation(_rec())
    assert result["grade"] == "A"
    assert result["hit"] is True
    assert result["action_adjusted_return"] == pytest.approx(0.20)


def test_sell_rewards_decline():
    result = grade_recommendation(_rec(action="SELL", realized=80.0))
    assert result["grade"] == "A"
    assert result["hit"] is True
    assert result["action_adjusted_return"] == pytest.approx(0.20)


def test_hold_rewards_stability_within_policy_tolerance():
    result = grade_recommendation(_rec(action="HOLD", realized=103.0))
    assert result["grade"] == "C"
    assert result["hit"] is True
    assert result["action_adjusted_return"] == pytest.approx(0.02)


def test_hold_penalizes_large_move_even_if_up():
    result = grade_recommendation(_rec(action="HOLD", realized=125.0))
    assert result["hit"] is False
    assert result["grade"] == "F"


def test_costs_are_applied_before_grading():
    policy = OutcomePolicy(exit_fee_rate=0.10, liquidity_haircut_rate=0.10)
    result = grade_recommendation(_rec(realized=120.0), policy=policy)
    assert result["net_realized_price"] == pytest.approx(97.2)
    assert result["action_adjusted_return"] == pytest.approx(-0.028)
    assert result["grade"] == "D"


def test_unsettled_and_pre_horizon_outcomes_fail_closed():
    unsettled = _rec()
    unsettled = Recommendation(**{**unsettled.__dict__, "realized_price": None, "realized_at": None})
    with pytest.raises(ValueError, match="settled"):
        grade_recommendation(unsettled)

    with pytest.raises(ValueError, match="predates"):
        grade_recommendation(_rec(realized_at=date(2026, 1, 15)))


def test_journal_packet_ignores_unsettled_and_segments_actions():
    unsettled = _rec(action="ACCUMULATE")
    unsettled = Recommendation(**{**unsettled.__dict__, "realized_price": None, "realized_at": None})
    packet = grade_journal([
        _rec(action="BUY", realized=120.0),
        _rec(action="SELL", realized=80.0),
        unsettled,
    ])
    assert packet["schema_version"] == "recommendation-outcomes.v1"
    assert packet["settled"] == 2
    assert packet["hit_rate"] == 1.0
    assert packet["grades"]["A"] == 2
    assert packet["actions"]["BUY"]["settled"] == 1
    assert packet["actions"]["SELL"]["settled"] == 1
    assert len(packet["packet_sha256"]) == 64


def test_scorecard_hash_is_order_independent_for_same_evidence():
    buy = _rec(action="BUY", realized=120.0)
    sell = _rec(action="SELL", realized=80.0)
    first = grade_journal([buy, sell])
    second = grade_journal([sell, buy])
    assert first == second
    assert first["packet_sha256"] == second["packet_sha256"]


def test_scorecard_hash_changes_when_outcome_or_policy_changes():
    baseline = grade_journal([_rec(realized=120.0)])
    outcome_changed = grade_journal([_rec(realized=121.0)])
    policy_changed = grade_journal(
        [_rec(realized=120.0)],
        policy=OutcomePolicy(exit_fee_rate=0.01),
    )
    assert baseline["packet_sha256"] != outcome_changed["packet_sha256"]
    assert baseline["packet_sha256"] != policy_changed["packet_sha256"]


def test_invalid_policy_fails_closed():
    with pytest.raises(ValueError, match="between 0 and 1"):
        grade_recommendation(_rec(), policy=OutcomePolicy(exit_fee_rate=1.2))

    with pytest.raises(ValueError, match="descend"):
        grade_recommendation(_rec(), policy=OutcomePolicy(grade_b_min=0.25))
