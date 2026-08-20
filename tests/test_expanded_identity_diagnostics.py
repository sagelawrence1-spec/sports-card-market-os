import json
from pathlib import Path

from entity_matcher import SportsCardEntityMatcher


ROOT = Path(__file__).resolve().parents[1]
ASSETS = json.loads((ROOT / "config" / "opportunity_assets.json").read_text())
CORPUS = json.loads((ROOT / "fixtures" / "public_ebay_identity_expanded_v1.json").read_text())


def test_report_observed_positive_misses_for_expanded_identity_corpus():
    matcher = SportsCardEntityMatcher()
    misses = []
    for row in CORPUS["rows"]:
        if not row["expected_match"]:
            continue
        decision = matcher.match(ASSETS[row["card_id"]], row["title"])
        if not decision.accepted:
            misses.append({
                "item_id": row["item_id"],
                "card_id": row["card_id"],
                "reason": decision.reason,
                "score": decision.score,
                "diagnostics": decision.diagnostics,
            })
    assert not misses, json.dumps(misses, sort_keys=True)
