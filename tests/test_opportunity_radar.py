import json
from pathlib import Path

import pytest

from opportunity_engine import OpportunityAction, OpportunityStage
from opportunity_radar import evaluate_live_observation


FIXTURE = Path(__file__).parents[1] / "fixtures" / "opportunities" / "2026-08-16-joshua-baez.json"


def test_live_baez_signal_surfaces_acceleration_but_waits_for_comps():
    payload = json.loads(FIXTURE.read_text())
    candidate = evaluate_live_observation(payload)

    assert candidate.thesis.stage == OpportunityStage.ACCELERATION
    assert candidate.decision == "WATCH_FOR_COMPS"
    assert candidate.blocking_reason == "authoritative_market_repricing_unverified"
    assert candidate.thesis.action in {OpportunityAction.ADD, OpportunityAction.START_POSITION, OpportunityAction.WATCH}
    assert [card.card_id for card in candidate.thesis.cards] == [
        "2022-bowman-chrome-prospects-bcp-112-joshua-baez",
        "2022-bowman-chrome-prospect-auto-cpa-jb-joshua-baez",
    ]


def test_verified_market_observation_can_emit_engine_action():
    payload = json.loads(FIXTURE.read_text())
    payload["market_price_verified"] = True
    payload["market_repricing_pct"] = 42
    candidate = evaluate_live_observation(payload)
    assert candidate.decision == "DO_NOT_CHASE"
    assert candidate.blocking_reason is None


def test_verified_market_flag_requires_repricing_measurement():
    payload = json.loads(FIXTURE.read_text())
    payload["market_price_verified"] = True
    with pytest.raises(ValueError, match="requires market_repricing_pct"):
        evaluate_live_observation(payload)


def test_live_observation_requires_web_provenance():
    payload = json.loads(FIXTURE.read_text())
    payload["source_urls"] = ["not-a-url"]
    with pytest.raises(ValueError, match="invalid source URL"):
        evaluate_live_observation(payload)
