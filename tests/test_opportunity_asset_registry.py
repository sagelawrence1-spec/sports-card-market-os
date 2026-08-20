import json
from pathlib import Path


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_every_public_radar_candidate_has_canonical_research_asset():
    radar = _load("alpha-web/public/data/opportunity-radar.json")
    assets = _load("config/opportunity_assets.json")

    assert radar["candidates"]
    for candidate in radar["candidates"]:
        card_id = candidate.get("card_id")
        assert card_id, f"Radar candidate {candidate['player']} is missing card_id"
        assert card_id in assets, f"Radar card {card_id} is missing from canonical opportunity assets"
        asset = assets[card_id]
        assert asset["card_id"] == card_id
        assert asset["player"] == candidate["player"]
        assert asset["label"] == candidate["card"]
        assert asset["manufacturer"]
        assert asset["set_name"]
        assert asset["card_number"]
        assert asset["parallel"]
        assert asset["autograph"] in (0, 1)


def test_opportunity_assets_are_directly_usable_by_research_runner():
    assets = _load("config/opportunity_assets.json")
    assert len(assets) == len(set(assets))
    for key, asset in assets.items():
        assert key == asset["card_id"]
        assert asset["registry_source"] == "live_opportunity_verified_identity"
