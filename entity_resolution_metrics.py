from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, Iterable

from entity_matcher import SportsCardEntityMatcher


def _family(asset: Dict[str, Any]) -> str:
    manufacturer = str(asset.get("manufacturer") or "unknown").strip() or "unknown"
    set_name = str(asset.get("set_name") or asset.get("set") or "unknown").strip() or "unknown"
    return f"{manufacturer}::{set_name}"


def _card_key(asset: Dict[str, Any]) -> str:
    card_id = str(asset.get("card_id") or "").strip()
    if card_id:
        return card_id
    parts = [
        str(asset.get("manufacturer") or "unknown").strip() or "unknown",
        str(asset.get("set_name") or asset.get("set") or "unknown").strip() or "unknown",
        str(asset.get("player") or "unknown").strip() or "unknown",
        str(asset.get("card_number") or "unknown").strip() or "unknown",
    ]
    return "::".join(parts)


def _new_bucket() -> Dict[str, Any]:
    return {
        "rows": 0,
        "positive_labels": 0,
        "negative_labels": 0,
        "accepted": 0,
        "manual_review": 0,
        "true_accepts": 0,
        "false_accepts": 0,
        "missed_positives": 0,
        "_decision_reasons": Counter(),
    }


def _finalize(bucket: Dict[str, Any]) -> Dict[str, Any]:
    rows = bucket["rows"]
    accepted = bucket["accepted"]
    positives = bucket["positive_labels"]
    negatives = bucket["negative_labels"]
    return {
        **{key: value for key, value in bucket.items() if key != "_decision_reasons"},
        "precision": round(bucket["true_accepts"] / accepted, 4) if accepted else None,
        "recall": round(bucket["true_accepts"] / positives, 4) if positives else None,
        "false_accept_rate": round(bucket["false_accepts"] / negatives, 4) if negatives else None,
        "review_rate": round(bucket["manual_review"] / rows, 4) if rows else None,
        "decision_reasons": dict(sorted(bucket["_decision_reasons"].items())),
    }


def evaluate_entity_resolution(
    rows: Iterable[Dict[str, Any]],
    matcher: SportsCardEntityMatcher | None = None,
) -> Dict[str, Any]:
    """Score definitive human labels against current matcher behavior.

    Each row must contain ``asset``, ``title``, and boolean ``expected_match``.
    This evaluator is intentionally read-only: it does not tune thresholds or learn
    aliases from the evaluated labels, keeping the measurement path leakage-safe.

    The report includes overall, family, and canonical-card slices. Per-card slices
    prevent a broad family score from hiding an unmeasured or one-sided card identity.
    Decision-reason histograms make observed misses inspectable without leaking labels
    back into matcher behavior.
    """

    matcher = matcher or SportsCardEntityMatcher()
    overall = _new_bucket()
    families: Dict[str, Dict[str, Any]] = defaultdict(_new_bucket)
    cards: Dict[str, Dict[str, Any]] = defaultdict(_new_bucket)

    for index, row in enumerate(rows):
        if not isinstance(row.get("expected_match"), bool):
            raise ValueError(f"row {index} expected_match must be boolean")
        asset = row.get("asset")
        title = row.get("title")
        if not isinstance(asset, dict) or not isinstance(title, str) or not title.strip():
            raise ValueError(f"row {index} requires asset dict and non-empty title")

        expected = row["expected_match"]
        decision = matcher.match(asset, title)
        family = _family(asset)
        card_key = _card_key(asset)

        for bucket in (overall, families[family], cards[card_key]):
            bucket["rows"] += 1
            bucket["positive_labels" if expected else "negative_labels"] += 1
            bucket["_decision_reasons"][decision.reason] += 1
            if decision.accepted:
                bucket["accepted"] += 1
                bucket["true_accepts" if expected else "false_accepts"] += 1
            elif expected:
                bucket["missed_positives"] += 1
            if decision.reason == "manual_review":
                bucket["manual_review"] += 1

    return {
        "schema": "entity-resolution-eval.v1",
        "overall": _finalize(overall),
        "by_family": {family: _finalize(bucket) for family, bucket in sorted(families.items())},
        "by_card": {card_id: _finalize(bucket) for card_id, bucket in sorted(cards.items())},
    }
