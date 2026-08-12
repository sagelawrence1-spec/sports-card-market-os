from market_contract import build_market_scan
from models import Signal


ASSETS = {
    "CARD-A": {
        "year": "2009",
        "manufacturer": "Topps",
        "set": "Chrome",
        "player": "Stephen Curry",
        "card_number": "101",
        "parallel": "Base",
        "grade_company": "PSA",
        "grade": "9",
    },
    "CARD-B": {
        "year": "2018",
        "manufacturer": "Topps",
        "set": "Chrome Update",
        "player": "Shohei Ohtani",
        "card_number": "HMT1",
        "parallel": "Base",
        "grade_company": "PSA",
        "grade": "10",
    },
}


def signal(card_id, classification, confidence, diagnostics):
    return Signal(
        observation_id=f"OBS-{card_id}",
        card_id=card_id,
        player=ASSETS[card_id]["player"],
        sport="NBA" if card_id == "CARD-A" else "MLB",
        signal=classification,
        confidence=confidence,
        ir_score=0,
        rar_score=0,
        mi_score=0,
        cie_score=0,
        alerts=["AOA"] if classification == "BUY" else [],
        thesis="Deterministic contract test.",
        diagnostics=diagnostics,
    )


def contract():
    signals = [
        signal("CARD-A", "BUY", 88, {
            "avg_price_30d": 4800,
            "price_change_30d": 0.08,
            "sales_30d": 12,
            "liquidity_score": 81,
            "volatility_30d": 0.08,
        }),
        signal("CARD-B", "WATCH", 64, {
            "avg_price_30d": 3100,
            "price_change_30d": 0.01,
            "sales_30d": 4,
            "liquidity_score": 49,
            "volatility_30d": 0.25,
        }),
    ]
    return build_market_scan(
        signals,
        source_kind="synthetic_fixture",
        source_label="Deterministic inline fixture",
        universe_size=len(signals),
        asset_lookup=ASSETS,
        generated_at="2026-08-12T12:00:00+00:00",
    )


def test_market_scan_contract_is_versioned_and_provenanced():
    result = contract()
    assert result["schema_version"] == "market-scan.v1"
    assert result["generated_at"] == "2026-08-12T12:00:00+00:00"
    assert result["source"] == {
        "kind": "synthetic_fixture",
        "label": "Deterministic inline fixture",
    }
    assert result["universe_size"] == len(result["items"])


def test_market_scan_items_preserve_engine_provenance():
    item = contract()["items"][0]
    assert item["observation_id"] == "OBS-CARD-A"
    assert item["card_id"] == "CARD-A"
    assert item["card"] == "2009 Topps Chrome Stephen Curry #101 · PSA 9"
    assert item["engine_classification"] == "BUY"
    assert item["evidence_grade"] == "A"
    assert item["accepted_sales_30d"] == 12


def test_non_actionable_engine_states_are_not_promoted_to_actions():
    watch = next(item for item in contract()["items"] if item["engine_classification"] == "WATCH")
    assert watch["action"] is None
    assert watch["fair_value"] == 3100
    assert watch["evidence_grade"] == "C"
