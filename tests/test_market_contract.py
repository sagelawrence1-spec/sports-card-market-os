from pathlib import Path

from data_provider import load_raw_bundle
from engine import analyze
from feature_engineering import derive_all
from market_contract import build_market_scan


FIXTURES = Path(__file__).resolve().parents[1] / "raw_test_data"


def contract():
    bundle = load_raw_bundle(FIXTURES)
    assets = bundle[0]
    features = derive_all(bundle)
    signals = [analyze(feature) for feature in features]
    return build_market_scan(
        signals,
        source_kind="synthetic_fixture",
        source_label="Deterministic test fixture",
        universe_size=len(features),
        asset_lookup=assets,
        generated_at="2026-08-12T12:00:00+00:00",
    )


def test_market_scan_contract_is_versioned_and_provenanced():
    result = contract()
    assert result["schema_version"] == "market-scan.v1"
    assert result["generated_at"] == "2026-08-12T12:00:00+00:00"
    assert result["source"] == {
        "kind": "synthetic_fixture",
        "label": "Deterministic test fixture",
    }
    assert result["universe_size"] == len(result["items"])


def test_market_scan_items_preserve_engine_provenance():
    item = contract()["items"][0]
    assert item["observation_id"]
    assert item["card_id"]
    assert item["card"].startswith(tuple(str(year) for year in range(1900, 2100)))
    assert item["engine_classification"]
    assert item["evidence_grade"] in {"A", "B", "C"}
    assert item["accepted_sales_30d"] >= 0


def test_non_actionable_engine_states_are_not_promoted_to_actions():
    items = contract()["items"]
    watch_or_avoid = [
        item for item in items if item["engine_classification"] in {"WATCH", "AVOID"}
    ]
    assert watch_or_avoid
    assert all(item["action"] is None for item in watch_or_avoid)
