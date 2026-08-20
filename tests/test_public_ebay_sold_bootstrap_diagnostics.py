import json
from pathlib import Path

from entity_matcher import SportsCardEntityMatcher


def _load_json(path):
    return json.loads(Path(path).read_text())


def test_public_ebay_bootstrap_positive_diagnostics():
    assets = _load_json("config/opportunity_assets.json")
    corpus = _load_json("fixtures/public_ebay_sold_bootstrap_v1.json")
    matcher = SportsCardEntityMatcher()

    diagnostics = []
    for evidence in corpus["rows"]:
        if not evidence["expected_match"]:
            continue
        decision = matcher.match(assets[evidence["card_id"]], evidence["title"])
        diagnostics.append({
            "item_id": evidence["item_id"],
            "title": evidence["title"],
            "accepted": decision.accepted,
            "reason": decision.reason,
            "score": decision.score,
            "diagnostics": decision.diagnostics,
        })

    accepted = sum(row["accepted"] for row in diagnostics)
    assert accepted / len(diagnostics) >= 0.80, diagnostics
