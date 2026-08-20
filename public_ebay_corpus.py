"""Fail-closed health report for public eBay identity-resolution corpora.

Public eBay pages are useful empirical identity evidence, but they are not a substitute
for authenticated Product Research price history. This module keeps those two claims
separate: matcher quality can pass while corpus breadth remains explicitly unready.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping

from entity_matcher import SportsCardEntityMatcher
from entity_resolution_metrics import evaluate_entity_resolution


_EBAY_ITEM_URL = re.compile(r"^https://www\.ebay\.com/itm/(\d+)(?:[/?#].*)?$")


@dataclass(frozen=True)
class PublicEbayCorpusPolicy:
    min_rows: int = 30
    min_rows_per_card: int = 4
    min_positive_per_card: int = 2
    min_negative_per_card: int = 2
    min_price_usable_rows: int = 5
    min_precision: float = 0.99
    min_recall: float = 0.80
    max_false_accepts: int = 0
    max_review_rate: float = 0.35
    require_all_assets: bool = True

    def __post_init__(self) -> None:
        for name in (
            "min_rows",
            "min_rows_per_card",
            "min_positive_per_card",
            "min_negative_per_card",
            "min_price_usable_rows",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.max_false_accepts < 0:
            raise ValueError("max_false_accepts must be non-negative")
        for name in ("min_precision", "min_recall", "max_review_rate"):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")


def validate_public_ebay_corpus(
    corpus: Mapping[str, Any],
    assets: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate provenance and fields without trusting the matcher or labels."""

    errors: list[str] = []
    rows = corpus.get("rows")
    if not isinstance(rows, list):
        return {"valid": False, "errors": ["rows_not_list"], "rows": 0}

    seen_item_ids: set[str] = set()
    seen_urls: set[str] = set()
    valid_rows = 0

    for index, row in enumerate(rows):
        prefix = f"row_{index}"
        if not isinstance(row, Mapping):
            errors.append(f"{prefix}:not_object")
            continue

        item_id = str(row.get("item_id") or "").strip()
        source_url = str(row.get("source_url") or "").strip()
        title = str(row.get("title") or "").strip()
        card_id = str(row.get("card_id") or "").strip()
        expected = row.get("expected_match")
        price_usable = row.get("price_usable")

        if not item_id.isdigit():
            errors.append(f"{prefix}:invalid_item_id")
        elif item_id in seen_item_ids:
            errors.append(f"{prefix}:duplicate_item_id")
        seen_item_ids.add(item_id)

        url_match = _EBAY_ITEM_URL.match(source_url)
        if not url_match:
            errors.append(f"{prefix}:invalid_ebay_item_url")
        elif item_id and url_match.group(1) != item_id:
            errors.append(f"{prefix}:item_url_id_mismatch")
        if source_url in seen_urls:
            errors.append(f"{prefix}:duplicate_source_url")
        seen_urls.add(source_url)

        if not title:
            errors.append(f"{prefix}:missing_title")
        if card_id not in assets:
            errors.append(f"{prefix}:unknown_card_id")
        if not isinstance(expected, bool):
            errors.append(f"{prefix}:expected_match_not_boolean")
        if not isinstance(price_usable, bool):
            errors.append(f"{prefix}:price_usable_not_boolean")
        elif price_usable:
            sold_price = row.get("sold_price")
            shipping = row.get("shipping")
            if not isinstance(sold_price, (int, float)) or sold_price <= 0:
                errors.append(f"{prefix}:usable_price_missing")
            if not isinstance(shipping, (int, float)) or shipping < 0:
                errors.append(f"{prefix}:usable_shipping_missing")

        if not any(value.startswith(f"{prefix}:") for value in errors):
            valid_rows += 1

    return {
        "valid": not errors,
        "errors": errors,
        "rows": len(rows),
        "valid_rows": valid_rows,
        "unique_item_ids": len(seen_item_ids),
        "unique_source_urls": len(seen_urls),
    }


def _overall_gate(metrics: Mapping[str, Any], policy: PublicEbayCorpusPolicy) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    if int(metrics.get("false_accepts") or 0) > policy.max_false_accepts:
        blockers.append("observed_false_accepts")
    precision = metrics.get("precision")
    recall = metrics.get("recall")
    review_rate = metrics.get("review_rate")
    if precision is None or precision < policy.min_precision:
        blockers.append("precision_below_floor")
    if recall is None or recall < policy.min_recall:
        blockers.append("recall_below_floor")
    if review_rate is None or review_rate > policy.max_review_rate:
        blockers.append("review_rate_above_ceiling")
    return not blockers, blockers


def _card_coverage(
    evaluation: Mapping[str, Any],
    assets: Mapping[str, Mapping[str, Any]],
    policy: PublicEbayCorpusPolicy,
) -> tuple[dict[str, Any], list[str]]:
    measured = evaluation.get("by_card") or {}
    required_ids = sorted(str(card_id) for card_id in assets) if policy.require_all_assets else sorted(measured)
    coverage: dict[str, Any] = {}
    blockers: list[str] = []

    for card_id in required_ids:
        metrics = dict(measured.get(card_id) or {})
        card_blockers: list[str] = []
        rows = int(metrics.get("rows") or 0)
        positives = int(metrics.get("positive_labels") or 0)
        negatives = int(metrics.get("negative_labels") or 0)
        if rows < policy.min_rows_per_card:
            card_blockers.append("insufficient_rows")
        if positives < policy.min_positive_per_card:
            card_blockers.append("insufficient_positive_labels")
        if negatives < policy.min_negative_per_card:
            card_blockers.append("insufficient_negative_labels")
        if card_blockers:
            blockers.append(f"card_coverage:{card_id}")
        coverage[card_id] = {
            "ready": not card_blockers,
            "blockers": card_blockers,
            "metrics": metrics,
        }

    return coverage, blockers


def build_public_ebay_corpus_report(
    corpus: Mapping[str, Any],
    assets: Mapping[str, Mapping[str, Any]],
    *,
    matcher: SportsCardEntityMatcher | None = None,
    policy: PublicEbayCorpusPolicy | None = None,
) -> dict[str, Any]:
    """Measure matcher quality and corpus breadth as independent release gates."""

    policy = policy or PublicEbayCorpusPolicy()
    validation = validate_public_ebay_corpus(corpus, assets)
    if not validation["valid"]:
        return {
            "schema": "public-ebay-corpus-report.v1",
            "ready": False,
            "matcher_gate_ready": False,
            "coverage_gate_ready": False,
            "blockers": ["invalid_corpus"],
            "validation": validation,
            "evaluation": None,
            "card_coverage": {},
        }

    rows = corpus["rows"]
    evaluation_rows = [
        {
            "asset": dict(assets[row["card_id"]]),
            "title": row["title"],
            "expected_match": row["expected_match"],
        }
        for row in rows
    ]
    evaluation = evaluate_entity_resolution(evaluation_rows, matcher=matcher or SportsCardEntityMatcher())
    matcher_ready, matcher_blockers = _overall_gate(evaluation["overall"], policy)
    card_coverage, coverage_blockers = _card_coverage(evaluation, assets, policy)

    blockers = list(matcher_blockers) + coverage_blockers
    if len(rows) < policy.min_rows:
        blockers.append("corpus_rows_below_floor")
    usable_prices = sum(1 for row in rows if row.get("price_usable") is True)
    if usable_prices < policy.min_price_usable_rows:
        blockers.append("price_sanity_subset_below_floor")

    coverage_ready = not coverage_blockers and len(rows) >= policy.min_rows
    return {
        "schema": "public-ebay-corpus-report.v1",
        "ready": matcher_ready and coverage_ready and usable_prices >= policy.min_price_usable_rows,
        "matcher_gate_ready": matcher_ready,
        "coverage_gate_ready": coverage_ready,
        "blockers": blockers,
        "validation": validation,
        "price_sanity_subset": {
            "usable_rows": usable_prices,
            "minimum": policy.min_price_usable_rows,
            "authoritative_product_research": False,
        },
        "policy": {
            "min_rows": policy.min_rows,
            "min_rows_per_card": policy.min_rows_per_card,
            "min_positive_per_card": policy.min_positive_per_card,
            "min_negative_per_card": policy.min_negative_per_card,
            "min_price_usable_rows": policy.min_price_usable_rows,
            "min_precision": policy.min_precision,
            "min_recall": policy.min_recall,
            "max_false_accepts": policy.max_false_accepts,
            "max_review_rate": policy.max_review_rate,
            "require_all_assets": policy.require_all_assets,
        },
        "evaluation": evaluation,
        "card_coverage": card_coverage,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure public eBay corpus health without overstating price authority.")
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--assets", default="config/opportunity_assets.json")
    parser.add_argument("--output")
    args = parser.parse_args()

    corpus = json.loads(Path(args.corpus).read_text())
    assets = json.loads(Path(args.assets).read_text())
    report = build_public_ebay_corpus_report(corpus, assets)
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(payload + "\n")
    else:
        print(payload)
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
