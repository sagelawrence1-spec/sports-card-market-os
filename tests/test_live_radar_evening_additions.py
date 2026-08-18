import json
from pathlib import Path

from opportunity_engine import OpportunityStage, ThesisType
from opportunity_radar import scan_live_observations


FIXTURE = Path(__file__).parents[1] / "fixtures" / "opportunities" / "2026-08-17-evening-radar-additions.json"


def test_evening_radar_additions_surface_confirmed_entry_stage_callups_without_forcing_actions():
    payloads = json.loads(FIXTURE.read_text())
    report = scan_live_observations(payloads)

    assert report.schema == "opportunity-radar-batch.v1"
    assert report.input_count == 2
    assert report.candidate_count == 2
    assert report.duplicate_count == 0
    assert report.failures == ()
    assert report.actionable_count == 0
    assert {candidate.thesis.player_id for candidate in report.candidates} == {
        "mlb-ethan-pecko",
        "mlb-matt-wilkinson",
    }
    assert all(candidate.thesis.thesis_type == ThesisType.CATALYST for candidate in report.candidates)
    assert all(candidate.thesis.stage == OpportunityStage.ENTRY for candidate in report.candidates)
    assert all(candidate.decision == "WATCH_FOR_COMPS" for candidate in report.candidates)
    assert all(candidate.blocking_reason == "authoritative_market_repricing_unverified" for candidate in report.candidates)


def test_evening_radar_additions_preserve_verified_card_expressions_and_sources():
    payloads = json.loads(FIXTURE.read_text())
    report = scan_live_observations(payloads)
    by_player = {candidate.thesis.player_id: candidate for candidate in report.candidates}

    pecko = by_player["mlb-ethan-pecko"]
    assert pecko.thesis.cards[0].card_id == "2025-bowman-chrome-prospect-auto-cpa-epe-ethan-pecko"
    assert any("houstonchronicle.com" in url for url in pecko.source_urls)

    wilkinson = by_player["mlb-matt-wilkinson"]
    assert [card.card_id for card in wilkinson.thesis.cards] == [
        "2025-bowman-chrome-prospects-bcp-145-matt-wilkinson",
        "2025-bowman-chrome-prospect-auto-cpa-mw-matt-wilkinson",
    ]
    assert any("reuters.com" in url for url in wilkinson.source_urls)
    assert any("beckett.com" in url for url in wilkinson.source_urls)
    assert wilkinson.market_price_verified is False
