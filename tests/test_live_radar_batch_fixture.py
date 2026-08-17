import json
from pathlib import Path

from opportunity_radar import scan_live_observations


FIXTURE = Path(__file__).parents[1] / "fixtures" / "opportunities" / "2026-08-17-live-radar-batch.json"


def test_sourced_live_radar_batch_surfaces_multiple_candidates_without_forcing_actions():
    payloads = json.loads(FIXTURE.read_text())
    report = scan_live_observations(payloads)

    assert report.schema == "opportunity-radar-batch.v1"
    assert report.input_count == 3
    assert report.candidate_count == 3
    assert report.duplicate_count == 0
    assert report.failures == ()
    assert report.actionable_count == 0
    assert {candidate.thesis.player_id for candidate in report.candidates} == {
        "mlb-joshua-baez",
        "mlb-kaelen-culpepper",
        "mlb-george-lombard-jr",
    }
    assert all(candidate.decision == "WATCH_FOR_COMPS" for candidate in report.candidates)
    assert all(candidate.blocking_reason == "authoritative_market_repricing_unverified" for candidate in report.candidates)


def test_sourced_live_radar_batch_preserves_card_expressions_and_source_provenance():
    payloads = json.loads(FIXTURE.read_text())
    report = scan_live_observations(payloads)
    by_player = {candidate.thesis.player_id: candidate for candidate in report.candidates}

    culpepper = by_player["mlb-kaelen-culpepper"]
    assert [card.card_id for card in culpepper.thesis.cards] == [
        "2024-bowman-draft-chrome-bdc-98-kaelen-culpepper",
        "2024-bowman-draft-chrome-prospect-auto-cpa-kc-kaelen-culpepper",
    ]
    assert any("reuters.com" in url for url in culpepper.source_urls)
    assert any("beckett.com" in url for url in culpepper.source_urls)

    lombard = by_player["mlb-george-lombard-jr"]
    assert lombard.thesis.cards[0].card_id == "2024-bowman-draft-chrome-bdc-118-george-lombard-jr"
    assert lombard.market_price_verified is False
