import copy

import pytest

from opportunity_outcomes import OpportunityOutcomePolicy, grade_opportunity_decision


def _packet():
    return {
        "schema": "opportunity-decision-packet.v1",
        "player_id": "player-1",
        "card": {"card_id": "card-10", "label": "2026 Bowman Chrome Player One #10"},
        "catalyst_at": "2026-08-10T12:00:00+00:00",
        "as_of": "2026-08-18T10:00:00+00:00",
        "decision": "START_POSITION",
        "actionable": True,
    }


def _collection():
    return {
        "schema": "opportunity-repricing-collection.v1",
        "player_id": "player-1",
        "card_id": "card-10",
        "verification": {
            "verified": True,
            "blocking_reason": None,
            "pre_median": 90.0,
            "post_median": 100.0,
            "repricing_pct": 11.111111,
            "catalyst_at": "2026-08-10T12:00:00+00:00",
            "as_of": "2026-08-18T10:00:00+00:00",
            "evidence_ids": ["EBAY_PRODUCT_RESEARCH:1"],
        },
    }


def test_grades_actionable_decision_from_original_authoritative_entry():
    outcome = grade_opportunity_decision(
        _packet(),
        _collection(),
        realized_price=125.0,
        realized_at="2026-09-20T10:00:00+00:00",
    )

    assert outcome["schema"] == "opportunity-outcome.v1"
    assert outcome["entry_price"] == 100.0
    assert outcome["net_return"] == pytest.approx(0.25)
    assert outcome["grade"] == "A"
    assert outcome["hit"] is True


def test_applies_exit_costs_before_grading():
    outcome = grade_opportunity_decision(
        _packet(),
        _collection(),
        realized_price=110.0,
        realized_at="2026-09-20T10:00:00+00:00",
        policy=OpportunityOutcomePolicy(exit_fee_rate=0.05, liquidity_haircut_rate=0.05),
    )

    assert outcome["net_realized_price"] == pytest.approx(99.275)
    assert outcome["net_return"] == pytest.approx(-0.00725)
    assert outcome["hit"] is False


def test_rejects_pre_horizon_outcome():
    with pytest.raises(ValueError, match="predates"):
        grade_opportunity_decision(
            _packet(),
            _collection(),
            realized_price=125.0,
            realized_at="2026-09-01T10:00:00+00:00",
        )


def test_rejects_non_actionable_decision():
    packet = _packet()
    packet["decision"] = "WATCH_FOR_COMPS"
    packet["actionable"] = False
    with pytest.raises(ValueError, match="actionable"):
        grade_opportunity_decision(
            packet,
            _collection(),
            realized_price=125.0,
            realized_at="2026-09-20T10:00:00+00:00",
        )


def test_rejects_mismatched_or_unverified_collection():
    collection = _collection()
    collection["card_id"] = "wrong-card"
    with pytest.raises(ValueError, match="card"):
        grade_opportunity_decision(
            _packet(),
            collection,
            realized_price=125.0,
            realized_at="2026-09-20T10:00:00+00:00",
        )

    collection = _collection()
    collection["verification"]["verified"] = False
    with pytest.raises(ValueError, match="verified"):
        grade_opportunity_decision(
            _packet(),
            collection,
            realized_price=125.0,
            realized_at="2026-09-20T10:00:00+00:00",
        )


def test_rejects_hindsight_substitution_of_collection_timestamp():
    collection = copy.deepcopy(_collection())
    collection["verification"]["as_of"] = "2026-08-19T10:00:00+00:00"
    with pytest.raises(ValueError, match="as_of"):
        grade_opportunity_decision(
            _packet(),
            collection,
            realized_price=125.0,
            realized_at="2026-09-20T10:00:00+00:00",
        )


def test_validates_policy():
    with pytest.raises(ValueError, match="min_horizon_days"):
        grade_opportunity_decision(
            _packet(),
            _collection(),
            realized_price=125.0,
            realized_at="2026-09-20T10:00:00+00:00",
            policy=OpportunityOutcomePolicy(min_horizon_days=0),
        )
