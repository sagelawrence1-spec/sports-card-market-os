import json
from pathlib import Path

from entity_matcher import SportsCardEntityMatcher
from entity_resolution_metrics import evaluate_entity_resolution


def _load_json(path):
    return json.loads(Path(path).read_text())


def test_public_ebay_sold_bootstrap_measures_real_matcher_behavior():
    assets = _load_json("config/opportunity_assets.json")
    corpus = _load_json("fixtures/public_ebay_sold_bootstrap_v1.json")

    rows = []
    for evidence in corpus["rows"]:
        rows.append({
            "card_id": evidence["card_id"],
            "asset": assets[evidence["card_id"]],
            "title": evidence["title"],
            "expected_match": evidence["expected_match"],
        })

    result = evaluate_entity_resolution(rows, matcher=SportsCardEntityMatcher())
    overall = result["overall"]
    assert overall["rows"] == len(corpus["rows"])
    assert overall["false_accepts"] == 0
    assert overall["precision"] >= 0.99
    assert overall["recall"] >= 0.80
    assert overall["review_rate"] <= 0.35

    # Aggregate performance must not conceal a canonical card that is unsafe or unusable.
    assert len(result["by_card"]) >= 6
    for card_id, metrics in result["by_card"].items():
        assert metrics["false_accepts"] == 0, (card_id, metrics)
        if metrics["positive_labels"]:
            assert metrics["recall"] >= 0.80, (card_id, metrics)
        if metrics["rows"] >= 3:
            assert metrics["review_rate"] <= 0.35, (card_id, metrics)


def test_public_bootstrap_price_subset_is_explicitly_non_product_research():
    corpus = _load_json("fixtures/public_ebay_sold_bootstrap_v1.json")
    usable = [row for row in corpus["rows"] if row["price_usable"]]
    assert len(usable) >= 5
    assert all(row["shipping"] is not None for row in usable)
    assert "without requiring authenticated Product Research access" in corpus["purpose"]
