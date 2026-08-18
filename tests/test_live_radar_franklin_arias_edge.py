import json
from pathlib import Path

from opportunity_engine import OpportunityStage, ThesisType
from opportunity_radar import scan_live_observations


FIXTURE = Path(__file__).parents[1] / "fixtures" / "opportunities" / "2026-08-17-night-franklin-arias.json"


def test_franklin_arias_surfaces_as_acceleration_edge_without_forcing_capital_action():
    payloads = json.loads(FIXTURE.read_text())
    report = scan_live_observations(payloads)

    assert report.schema == "opportunity-radar-batch.v1"
    assert report.input_count == 1
    assert report.candidate_count == 1
    assert report.duplicate_count == 0
    assert report.failures == ()
    assert report.actionable_count == 0

    candidate = report.candidates[0]
    assert candidate.thesis.player_id == "mlb-franklin-arias"
    assert candidate.thesis.thesis_type == ThesisType.EDGE
    assert candidate.thesis.stage == OpportunityStage.ACCELERATION
    assert candidate.decision == "WATCH_FOR_COMPS"
    assert candidate.blocking_reason == "authoritative_market_repricing_unverified"
    assert candidate.market_price_verified is False


def test_franklin_arias_fixture_preserves_point_in_time_sources_and_target_card():
    payloads = json.loads(FIXTURE.read_text())
    candidate = scan_live_observations(payloads).candidates[0]

    assert candidate.observed_at.isoformat() == "2026-08-14T14:30:00+00:00"
    assert [card.card_id for card in candidate.thesis.cards] == [
        "2025-bowman-chrome-prospect-auto-cpa-fa-franklin-arias"
    ]
    assert any("overthemonster.com" in url for url in candidate.source_urls)
    assert any("mlb.com/news/red-sox-promoting-franklin-arias" in url for url in candidate.source_urls)
    assert any("psacard.com" in url for url in candidate.source_urls)
    assert "Triple-A" in candidate.thesis.why_now
    assert "No. 7" in candidate.thesis.why_now
