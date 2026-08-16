from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable

from entity_matcher import SportsCardEntityMatcher


def _family(asset: Dict[str, Any]) -> str:
    manufacturer = str(asset.get("manufacturer") or "unknown").strip() or "unknown"
    set_name = str(asset.get("set_name") or asset.get("set") or "unknown").strip() or "unknown"
    return f"{manufacturer}::{set_name}"


def _new_bucket() -> Dict[str, int]:
    return {
        "rows": 0,
        "positive_labels": 0,
        "negative_labels": 0,
        "accepted": 0,
        "manual_review": 0,
        "true_accepts": 0,
        "false_accepts": 0,
        "missed_positives": 0,
    }


def _finalize(bucket: Dict[str, int]) -> Dict[str, Any]:
    rows = bucket["rows"]
    accepted = bucket["accepted"]
    positives = bucket["positive_labels"]
    negatives = bucket["negative_labels"]
    return {
        **bucket,
        "precision": round(bucket["true_accepts"] / accepted, 4) if accepted else None,
        "recall": round(bucket["true_accepts"] / positives, 4) if positives else None,
        "false_accept_rate": round(bucket["false_accepts"] / negatives, 4) if negatives else None,
        "review_rate": round(bucket["manual_review"] / rows, 4) if rows else None,
    }


def evaluate_entity_resolution(
    rows: Iterable[Dict[str, Any]],
    matcher: SportsCardEntityMatcher | None = None,
) -> Dict[str, Any]:
    """Score definitive human labels against current matcher behavior.

    Each row must contain ``asset``, ``title``, and boolean ``expected_match``.
    This evaluator is intentionally read-only: it does not tune thresholds or learn
    aliases from the evaluated labels, keeping the measurement path leakage-safe.
    """

    matcher = matcher or SportsCardEntityMatcher()
    overall = _new_bucket()
    families: Dict[str, Dict[str, int]] = defaultdict(_new_bucket)

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

        for bucket in (overall, families[family]):
            bucket["rows"] += 1
            bucket["positive_labels" if expected else "negative_labels"] += 1
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
    }
