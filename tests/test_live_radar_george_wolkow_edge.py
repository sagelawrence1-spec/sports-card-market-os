import json
from pathlib import Path

from opportunity_engine import OpportunityStage, ThesisType
from opportunity_radar import scan_live_observations


FIXTURE = Path(__file__).parents[1] / "fixtures" / "opportunities" / "2026-08-18-evening-george-wolkow.json"


def test_george_wolkow_surfaces_as_acceleration_edge_without_forcing_capital_action():
    payloads = json.loads(FIXTURE.read_text())
    report = scan_live_observations(payloads)

    assert report.schema == "opportunity-radar-batch.v1"
    assert report.input_count == 1
    assert report.candidate_count == 1
    assert report.duplicate_count == 0
    assert report.failures == ()
    assert report.actionable_count == 0

    candidate = report.candidates[0]
    assert candidate.thesis.player_id == "mlb-george-wolkow"
    assert candidate.thesis.thesis_type == ThesisType.EDGE
    assert candidate.thesis.stage == OpportunityStage.ACCELERATION
    assert candidate.decision == "WATCH_FOR_COMPS"
    assert candidate.blocking_reason == "authoritative_market_repricing_unverified"
    assert candidate.market_price_verified is False


def test_george_wolkow_fixture_preserves_single_source_catalyst_and_target_card():
    payloads = json.loads(FIXTURE.read_text())
    candidate = scan_live_observations(payloads).candidates[0]

    assert payloads[0]["observed_at"] == "2026-08-18T23:59:00+00:00"
    assert [card.card_id for card in candidate.thesis.cards] == [
        "2024-bowman-chrome-prospect-auto-cpa-gwo-george-wolkow"
    ]
    assert any("southsidesox.com" in url for url in candidate.source_urls)
    assert any("beckett.com/news/2024-bowman-baseball-cards" in url for url in candidate.source_urls)
    assert candidate.source_quality == "SINGLE_SOURCE"
    assert candidate.source_host_count == 1
    assert "two-homer" in candidate.thesis.why_now
    assert "pre-MLB" in candidate.thesis.why_now
