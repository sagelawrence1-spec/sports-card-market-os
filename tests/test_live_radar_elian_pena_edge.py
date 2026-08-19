import json
from pathlib import Path

from opportunity_engine import OpportunityStage, ThesisType
from opportunity_radar import scan_live_observations


FIXTURE = Path(__file__).parents[1] / "fixtures" / "opportunities" / "2026-08-18-evening-elian-pena.json"


def test_elian_pena_surfaces_as_acceleration_edge_without_forcing_capital_action():
    payloads = json.loads(FIXTURE.read_text())
    report = scan_live_observations(payloads)

    assert report.schema == "opportunity-radar-batch.v1"
    assert report.input_count == 1
    assert report.candidate_count == 1
    assert report.duplicate_count == 0
    assert report.failures == ()
    assert report.actionable_count == 0

    candidate = report.candidates[0]
    assert candidate.thesis.player_id == "mlb-elian-pena"
    assert candidate.thesis.thesis_type == ThesisType.EDGE
    assert candidate.thesis.stage == OpportunityStage.ACCELERATION
    assert candidate.decision == "WATCH_FOR_COMPS"
    assert candidate.blocking_reason == "authoritative_market_repricing_unverified"
    assert candidate.market_price_verified is False


def test_elian_pena_fixture_preserves_point_in_time_sources_and_target_card():
    payloads = json.loads(FIXTURE.read_text())
    candidate = scan_live_observations(payloads).candidates[0]

    assert payloads[0]["observed_at"] == "2026-08-18T23:59:00+00:00"
    assert [card.card_id for card in candidate.thesis.cards] == [
        "2025-bowman-chrome-prospect-auto-cpa-ep-elian-pena"
    ]
    assert any("amazinavenue.com" in url for url in candidate.source_urls)
    assert any("beckett.com/news/2025-bowman-chrome-baseball-cards" in url for url in candidate.source_urls)
    assert "18" in candidate.thesis.why_now
    assert "High-A" in candidate.thesis.why_now
    assert "three-homer" in candidate.thesis.why_now
