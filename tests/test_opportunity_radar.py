import json
from pathlib import Path

import pytest

from opportunity_engine import OpportunityAction, OpportunityStage
from opportunity_radar import evaluate_live_observation, scan_live_observations


FIXTURE = Path(__file__).parents[1] / "fixtures" / "opportunities" / "2026-08-16-joshua-baez.json"


def _payload():
    return json.loads(FIXTURE.read_text())


def test_live_baez_signal_surfaces_acceleration_but_waits_for_comps():
    payload = _payload()
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
    payload = _payload()
    payload["market_price_verified"] = True
    payload["market_repricing_pct"] = 42
    candidate = evaluate_live_observation(payload)
    assert candidate.decision == "DO_NOT_CHASE"
    assert candidate.blocking_reason is None


def test_verified_market_flag_requires_repricing_measurement():
    payload = _payload()
    payload["market_price_verified"] = True
    with pytest.raises(ValueError, match="requires market_repricing_pct"):
        evaluate_live_observation(payload)


def test_live_observation_requires_web_provenance():
    payload = _payload()
    payload["source_urls"] = ["not-a-url"]
    with pytest.raises(ValueError, match="invalid source URL"):
        evaluate_live_observation(payload)


def test_batch_scan_preserves_valid_candidates_when_one_row_is_bad():
    good = _payload()
    bad = _payload()
    bad["player_id"] = "broken-row"
    bad["headline"] = "Malformed candidate"
    bad["source_urls"] = ["not-a-url"]

    report = scan_live_observations([bad, good])

    assert report.schema == "opportunity-radar-batch.v1"
    assert report.input_count == 2
    assert report.candidate_count == 1
    assert report.candidates[0].thesis.player_id == good["player_id"]
    assert len(report.failures) == 1
    assert report.failures[0].player_id == "broken-row"
    assert "invalid source URL" in report.failures[0].reason


def test_batch_scan_collapses_duplicate_catalyst_events():
    payload = _payload()
    duplicate = _payload()

    report = scan_live_observations([payload, duplicate])

    assert report.input_count == 2
    assert report.candidate_count == 1
    assert report.duplicate_count == 1
    assert report.failures == ()


def test_batch_scan_ranks_candidates_by_edge_then_evidence():
    lower = _payload()
    lower["player_id"] = "lower-edge"
    lower["player"] = "Lower Edge"
    lower["headline"] = "Lower edge catalyst"
    lower["factors"]["upside_asymmetry"] = 20
    lower["factors"]["hobby_lag"] = 20

    higher = _payload()
    higher["player_id"] = "higher-edge"
    higher["player"] = "Higher Edge"
    higher["headline"] = "Higher edge catalyst"
    higher["factors"]["upside_asymmetry"] = 95
    higher["factors"]["hobby_lag"] = 95

    report = scan_live_observations([lower, higher])

    assert [candidate.thesis.player_id for candidate in report.candidates] == ["higher-edge", "lower-edge"]


def test_unverified_batch_candidate_is_not_counted_as_actionable():
    report = scan_live_observations([_payload()])
    assert report.actionable_count == 0
