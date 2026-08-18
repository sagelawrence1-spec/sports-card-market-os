import json
from pathlib import Path

from opportunity_engine import OpportunityStage, ThesisType
from opportunity_radar import scan_live_observations


FIXTURE = Path(__file__).parents[1] / "fixtures" / "opportunities" / "2026-08-18-kaytron-allen.json"


def test_kaytron_allen_surfaces_as_nfl_acceleration_edge_without_forcing_capital_action():
    payloads = json.loads(FIXTURE.read_text())
    report = scan_live_observations(payloads)

    assert report.schema == "opportunity-radar-batch.v1"
    assert report.input_count == 1
    assert report.candidate_count == 1
    assert report.duplicate_count == 0
    assert report.failures == ()
    assert report.actionable_count == 0

    candidate = report.candidates[0]
    assert candidate.thesis.player_id == "nfl-kaytron-allen"
    assert candidate.thesis.thesis_type == ThesisType.EDGE
    assert candidate.thesis.stage == OpportunityStage.ACCELERATION
    assert candidate.decision == "WATCH_FOR_COMPS"
    assert candidate.blocking_reason == "authoritative_market_repricing_unverified"
    assert candidate.market_price_verified is False


def test_kaytron_allen_fixture_preserves_nfl_sources_and_primary_card_expression():
    payloads = json.loads(FIXTURE.read_text())
    candidate = scan_live_observations(payloads).candidates[0]

    assert payloads[0]["sport"] == "NFL"
    assert payloads[0]["observed_at"] == "2026-08-15T23:00:00+00:00"
    assert [card.card_id for card in candidate.thesis.cards] == [
        "2025-bowman-chrome-university-prospect-auto-bca-ka-kaytron-allen"
    ]
    assert any("reuters.com" in url for url in candidate.source_urls)
    assert any("nfl.com/players/kaytron-allen" in url for url in candidate.source_urls)
    assert any("beckett.com" in url for url in candidate.source_urls)
    assert "regular season" in candidate.thesis.why_now
