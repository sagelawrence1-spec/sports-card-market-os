import json
from pathlib import Path

from public_ebay_corpus import build_public_ebay_corpus_report


ROOT = Path(__file__).resolve().parents[1]
ASSETS = json.loads((ROOT / "config" / "opportunity_assets.json").read_text())
CORPUS = json.loads((ROOT / "fixtures" / "public_ebay_identity_expanded_v1.json").read_text())


def test_expanded_public_identity_corpus_is_balanced_and_valid():
    report = build_public_ebay_corpus_report(CORPUS, ASSETS)

    assert report["validation"]["valid"] is True, report["validation"]
    assert report["validation"]["rows"] == 30
    assert report["coverage_gate_ready"] is True, report["card_coverage"]
    assert len(report["card_coverage"]) == len(ASSETS) == 6

    for card_id, coverage in report["card_coverage"].items():
        metrics = coverage["metrics"]
        assert coverage["ready"] is True, (card_id, coverage)
        assert metrics["rows"] == 5
        assert metrics["positive_labels"] >= 2
        assert metrics["negative_labels"] >= 2


def test_expanded_public_identity_corpus_clears_matcher_quality_gate():
    report = build_public_ebay_corpus_report(CORPUS, ASSETS)

    assert report["matcher_gate_ready"] is True, {
        "blockers": report["blockers"],
        "overall": report["evaluation"]["overall"],
        "by_card": report["evaluation"]["by_card"],
    }
    assert report["ready"] is True, report
    assert report["price_sanity_subset"]["authoritative_product_research"] is False
