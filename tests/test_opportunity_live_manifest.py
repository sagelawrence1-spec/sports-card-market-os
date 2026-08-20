import json
from pathlib import Path

import pytest

from opportunity_live_manifest import build_live_research_manifest, main


ROOT = Path(__file__).resolve().parents[1]
RADAR_PATH = ROOT / "alpha-web" / "public" / "data" / "opportunity-radar.json"
ASSETS_PATH = ROOT / "config" / "opportunity_assets.json"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_public_radar_builds_exact_product_research_queue():
    result = build_live_research_manifest(_load(RADAR_PATH), assets=_load(ASSETS_PATH))

    assert result["schema"] == "opportunity-live-research-manifest.v1"
    assert result["candidate_count"] == 6
    plan = result["repricing_plan"]
    manifest = result["collection_manifest"]
    assert plan["request_count"] == 6
    assert manifest["selected_request_count"] == 6
    assert manifest["priority_counts"] == {"P0": 0, "P1": 6, "P2": 0}

    radar = _load(RADAR_PATH)
    expected_cards = {row["card_id"] for row in radar["candidates"]}
    assert {row["card_id"] for row in manifest["items"]} == expected_cards
    assert all(row["repricing_request"]["source_type"] == "EBAY_PRODUCT_RESEARCH" for row in manifest["items"])
    assert all(row["expected_export_filename"].endswith(".csv") for row in manifest["items"])

    by_player = {row["player"]: row for row in manifest["items"]}
    assert by_player["Elian Pena"]["search_query"] == "2025 Elian Pena Bowman Chrome CPA-EP autograph"
    assert by_player["George Wolkow"]["search_query"] == "2024 George Wolkow Bowman Chrome CPA-GWO autograph"
    assert by_player["Kaytron Allen"]["search_query"] == "2025 Kaytron Allen Bowman Chrome University BCA-KA autograph"
    assert by_player["Franklin Arias"]["search_query"] == "2025 Franklin Arias Bowman Chrome CPA-FA autograph"
    assert by_player["Bo Davidson"]["search_query"] == "2025 Bo Davidson Bowman Chrome CPA-BD autograph"
    assert by_player["Caleb Bonemer"]["search_query"] == "2024 Caleb Bonemer Bowman Draft Chrome CPA-CBO autograph"
    assert all(row["repricing_request"]["search_query"] == row["search_query"] for row in manifest["items"])
    assert all(row["search_query"] in row["collection_instruction"] for row in manifest["items"])


def test_public_radar_requires_canonical_asset_for_every_card():
    radar = _load(RADAR_PATH)
    assets = _load(ASSETS_PATH)
    assets.pop(radar["candidates"][0]["card_id"])

    with pytest.raises(ValueError, match="no canonical research asset"):
        build_live_research_manifest(radar, assets=assets)


def test_public_radar_rejects_asset_player_drift():
    radar = _load(RADAR_PATH)
    assets = _load(ASSETS_PATH)
    card_id = radar["candidates"][0]["card_id"]
    assets[card_id]["player"] = "Different Player"

    with pytest.raises(ValueError, match="player mismatch"):
        build_live_research_manifest(radar, assets=assets)


def test_public_radar_rejects_incomplete_search_identity():
    radar = _load(RADAR_PATH)
    assets = _load(ASSETS_PATH)
    card_id = radar["candidates"][0]["card_id"]
    assets[card_id].pop("card_number")

    with pytest.raises(ValueError, match="requires player, integer year, set_name, and card_number"):
        build_live_research_manifest(radar, assets=assets)


def test_public_radar_rejects_future_observation():
    radar = _load(RADAR_PATH)
    radar["candidates"][0]["observed_at"] = "2026-08-21T00:00:00Z"

    with pytest.raises(ValueError, match="after generated_at"):
        build_live_research_manifest(radar, assets=_load(ASSETS_PATH))


def test_cli_emits_live_collection_manifest(tmp_path):
    output = tmp_path / "manifest.json"
    rc = main([
        "--radar", str(RADAR_PATH),
        "--assets", str(ASSETS_PATH),
        "-o", str(output),
    ])
    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["collection_manifest"]["selected_request_count"] == 6
    assert all(item["search_query"] for item in payload["collection_manifest"]["items"])
