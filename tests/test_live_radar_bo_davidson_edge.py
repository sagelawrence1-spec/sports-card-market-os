import json
from pathlib import Path

from opportunity_engine import OpportunityStage, ThesisType
from opportunity_radar import scan_live_observations


FIXTURE = Path(__file__).parents[1] / "fixtures" / "opportunities" / "2026-08-17-night-bo-davidson.json"


def test_bo_davidson_breakout_surfaces_as_acceleration_edge_without_forcing_capital_action():
    payloads = json.loads(FIXTURE.read_text())
    report = scan_live_observations(payloads)

    assert report.schema == "opportunity-radar-batch.v1"
    assert report.input_count == 1
    assert report.candidate_count == 1
    assert report.duplicate_count == 0
    assert report.failures == ()
    assert report.actionable_count == 0

    candidate = report.candidates[0]
    assert candidate.thesis.player_id == "mlb-bo-davidson"
    assert candidate.thesis.thesis_type == ThesisType.EDGE
    assert candidate.thesis.stage == OpportunityStage.ACCELERATION
    assert candidate.decision == "WATCH_FOR_COMPS"
    assert candidate.blocking_reason == "authoritative_market_repricing_unverified"
    assert candidate.market_price_verified is False


def test_bo_davidson_fixture_preserves_source_provenance_and_target_card():
    payloads = json.loads(FIXTURE.read_text())
    candidate = scan_live_observations(payloads).candidates[0]

    assert [card.card_id for card in candidate.thesis.cards] == [
        "2025-bowman-chrome-prospect-auto-cpa-bd-bo-davidson"
    ]
    assert any("mccoveychronicles.com" in url for url in candidate.source_urls)
    assert any("mlb.com/milb/prospects" in url for url in candidate.source_urls)
    assert any("sportscardspro.com" in url for url in candidate.source_urls)
    assert "Triple-A" in candidate.thesis.why_now
