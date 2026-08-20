import json
from pathlib import Path

from entity_resolution_metrics import evaluate_entity_resolution
from public_ebay_corpus import (
    PRICE_SANITY_ROLE,
    PublicEbayCorpusPolicy,
    build_public_ebay_corpus_report,
    validate_public_ebay_corpus,
)


ROOT = Path(__file__).resolve().parents[1]
ASSETS = json.loads((ROOT / "config" / "opportunity_assets.json").read_text())
CORPUS = json.loads((ROOT / "fixtures" / "public_ebay_sold_bootstrap_v1.json").read_text())


def test_real_bootstrap_passes_matcher_quality_but_fails_breadth_gate():
    report = build_public_ebay_corpus_report(CORPUS, ASSETS)

    assert report["validation"]["valid"] is True
    assert report["matcher_gate_ready"] is True
    assert report["coverage_gate_ready"] is False
    assert report["ready"] is False
    assert "corpus_rows_below_floor" in report["blockers"]

    george = report["card_coverage"]["2024-bowman-chrome-prospect-auto-cpa-gwo-george-wolkow"]
    kaytron = report["card_coverage"]["2025-bowman-chrome-university-prospect-auto-bca-ka-kaytron-allen"]
    assert "insufficient_positive_labels" in george["blockers"]
    assert "insufficient_negative_labels" in kaytron["blockers"]

    # The public-price subset remains deliberately weaker than Product Research.
    assert report["price_sanity_subset"]["usable_rows"] >= 5
    assert report["price_sanity_subset"]["required_evidence_role"] == PRICE_SANITY_ROLE
    assert report["price_sanity_subset"]["authoritative_product_research"] is False


def test_relaxed_breadth_policy_does_not_change_measured_matcher_metrics():
    strict = build_public_ebay_corpus_report(CORPUS, ASSETS)
    relaxed = build_public_ebay_corpus_report(
        CORPUS,
        ASSETS,
        policy=PublicEbayCorpusPolicy(
            min_rows=len(CORPUS["rows"]),
            min_rows_per_card=1,
            min_positive_per_card=0,
            min_negative_per_card=0,
            min_price_usable_rows=5,
        ),
    )

    assert relaxed["ready"] is True
    assert relaxed["evaluation"]["overall"] == strict["evaluation"]["overall"]


def test_validation_rejects_duplicate_provenance_and_fake_price_usability():
    corpus = json.loads(json.dumps(CORPUS))
    corpus["rows"][1]["item_id"] = corpus["rows"][0]["item_id"]
    corpus["rows"][1]["source_url"] = corpus["rows"][0]["source_url"]
    corpus["rows"][1]["price_usable"] = True
    corpus["rows"][1]["shipping"] = None

    validation = validate_public_ebay_corpus(corpus, ASSETS)
    assert validation["valid"] is False
    assert any(value.endswith("duplicate_item_id") for value in validation["errors"])
    assert any(value.endswith("duplicate_source_url") for value in validation["errors"])
    assert any(value.endswith("identity_only_price_escalation") for value in validation["errors"])
    assert any(value.endswith("usable_shipping_missing") for value in validation["errors"])

    report = build_public_ebay_corpus_report(corpus, ASSETS)
    assert report["ready"] is False
    assert report["evaluation"] is None
    assert report["blockers"] == ["invalid_corpus"]


def test_validation_rejects_missing_or_mismatched_evidence_authority():
    missing_role = json.loads(json.dumps(CORPUS))
    missing_role["rows"][0].pop("evidence_role")
    validation = validate_public_ebay_corpus(missing_role, ASSETS)
    assert any(value.endswith("invalid_evidence_role") for value in validation["errors"])

    downgraded_price = json.loads(json.dumps(CORPUS))
    downgraded_price["rows"][0]["price_usable"] = False
    validation = validate_public_ebay_corpus(downgraded_price, ASSETS)
    assert any(value.endswith("price_sanity_role_not_usable") for value in validation["errors"])


def test_entity_resolution_report_exposes_per_card_reason_histograms():
    class Matcher:
        def match(self, asset, title):
            class Decision:
                accepted = "accept" in title
                reason = "accepted" if accepted else "manual_review"

            return Decision()

    rows = [
        {
            "asset": {"card_id": "card-a", "manufacturer": "Topps", "set_name": "Chrome"},
            "title": "accept one",
            "expected_match": True,
        },
        {
            "asset": {"card_id": "card-a", "manufacturer": "Topps", "set_name": "Chrome"},
            "title": "review one",
            "expected_match": True,
        },
        {
            "asset": {"card_id": "card-b", "manufacturer": "Topps", "set_name": "Chrome"},
            "title": "accept negative",
            "expected_match": False,
        },
    ]
    result = evaluate_entity_resolution(rows, matcher=Matcher())

    assert result["by_card"]["card-a"]["rows"] == 2
    assert result["by_card"]["card-a"]["decision_reasons"] == {"accepted": 1, "manual_review": 1}
    assert result["by_card"]["card-b"]["false_accepts"] == 1
    assert result["overall"]["decision_reasons"] == {"accepted": 2, "manual_review": 1}
