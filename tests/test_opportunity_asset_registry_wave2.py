import json
from pathlib import Path

from entity_matcher import SportsCardEntityMatcher


ROOT = Path(__file__).resolve().parents[1]
ASSETS = json.loads((ROOT / "config" / "opportunity_assets.json").read_text())
MATCHER = SportsCardEntityMatcher()

CASES = [
    (
        "fixtures/opportunities/2026-08-17-night-franklin-arias.json",
        "2025-bowman-chrome-prospect-auto-cpa-fa-franklin-arias",
        "Franklin Arias",
        "Bowman Chrome",
        "CPA-FA",
    ),
    (
        "fixtures/opportunities/2026-08-17-night-bo-davidson.json",
        "2025-bowman-chrome-prospect-auto-cpa-bd-bo-davidson",
        "Bo Davidson",
        "Bowman Chrome",
        "CPA-BD",
    ),
    (
        "fixtures/opportunities/2026-08-17-late-caleb-bonemer.json",
        "2024-bowman-draft-chrome-prospect-auto-cpa-cbo-caleb-bonemer",
        "Caleb Bonemer",
        "Bowman Draft Chrome",
        "CPA-CBO",
    ),
]


def test_wave2_live_opportunity_cards_have_canonical_research_assets():
    for fixture_path, card_id, player, set_name, card_number in CASES:
        observation = json.loads((ROOT / fixture_path).read_text())[0]
        assert observation["cards"][0]["card_id"] == card_id

        asset = ASSETS[card_id]
        assert asset["card_id"] == card_id
        assert asset["player"] == player
        assert asset["set_name"] == set_name
        assert asset["card_number"] == card_number
        assert asset["autograph"] == 1
        assert asset["registry_source"] == "live_opportunity_verified_identity"


def test_wave2_canonical_labels_are_accepted_by_entity_matcher():
    for _, card_id, *_ in CASES:
        asset = ASSETS[card_id]
        decision = MATCHER.match(asset, asset["label"])
        assert decision.accepted is True, (card_id, decision.reason, decision.diagnostics)
