"""Bind routing proof to the exact authoritative Product Research export bytes.

`corpus_proof.build_corpus_proof_report` remains useful for leakage-safe in-memory
measurement. This wrapper is the authoritative file-based path: it creates the hardened
Product Research receipt, verifies that receipt against the same export path, binds the
candidate registry and adjudicated label set used for proof generation, then builds the
routing proof only after the source binding is proven.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from corpus_proof import ProofPolicy, build_corpus_proof_report, load_delimited_export
from product_research_receipt import build_receipt

SCHEMA = "product-research-corpus-proof.v1"
EXPECTED_PROVIDER = "ebay_product_research"
EXPECTED_PRICE_BASIS = "sold_price_plus_shipping"


def _fingerprint(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _manifest_binding(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Fingerprint proof inputs independent of mapping key order.

    List order remains significant because corpus selection and label adjudication are
    ordered inputs to proof generation. Mapping key order is normalized so semantically
    identical JSON objects produce the same binding.
    """

    canonical = json.dumps(
        rows,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return {
        "sha256": hashlib.sha256(canonical).hexdigest(),
        "rows": len(rows),
        "canonical_bytes": len(canonical),
    }


def _verify_receipt_source(path: Path, receipt: Mapping[str, Any], *, proof_input_rows: int) -> dict[str, Any]:
    source = receipt.get("source")
    rows = receipt.get("rows")
    if not isinstance(source, Mapping) or not isinstance(rows, Mapping):
        raise ValueError("Product Research receipt is missing source or row-accounting metadata")

    expected_sha = str(source.get("sha256") or "").strip()
    expected_size = source.get("size_bytes")
    receipt_raw_rows = rows.get("raw")
    if not expected_sha or not isinstance(expected_size, int):
        raise ValueError("Product Research receipt has invalid source fingerprint")
    if not isinstance(receipt_raw_rows, int):
        raise ValueError("Product Research receipt has invalid raw row count")

    current_sha, current_size = _fingerprint(path)
    if current_sha != expected_sha or current_size != expected_size:
        raise ValueError("Product Research export changed after receipt and before proof completion")
    if receipt_raw_rows != proof_input_rows:
        raise ValueError(
            f"Product Research receipt/proof row mismatch: receipt={receipt_raw_rows} proof={proof_input_rows}"
        )
    if receipt.get("provider") != EXPECTED_PROVIDER:
        raise ValueError("routing proof requires the authoritative eBay Product Research provider")
    if receipt.get("price_basis") != EXPECTED_PRICE_BASIS:
        raise ValueError("routing proof requires sold-price-plus-shipping Product Research evidence")

    return {
        "verified": True,
        "sha256": expected_sha,
        "size_bytes": expected_size,
        "raw_rows": receipt_raw_rows,
        "provider": EXPECTED_PROVIDER,
        "price_basis": EXPECTED_PRICE_BASIS,
    }


def build_product_research_corpus_proof(
    export_path: str | Path,
    candidates: list[Mapping[str, Any]],
    label_rows: list[Mapping[str, Any]],
    *,
    policy: ProofPolicy | None = None,
    seed: str = "routing-corpus-v1",
    query: str = "",
) -> dict[str, Any]:
    """Build a leakage-safe routing proof bound to exact export, candidates, and labels."""

    source = Path(export_path)
    receipt = build_receipt(source, query=query)
    raw_rows = load_delimited_export(source)
    binding = _verify_receipt_source(source, receipt, proof_input_rows=len(raw_rows))
    proof_inputs = {
        "candidates": _manifest_binding(candidates),
        "labels": _manifest_binding(label_rows),
    }
    proof = build_corpus_proof_report(raw_rows, candidates, label_rows, policy=policy, seed=seed)

    return {
        **proof,
        "authoritative_source": {
            "schema": SCHEMA,
            "binding": binding,
            "receipt": receipt,
            "proof_inputs": proof_inputs,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a routing proof bound to exact eBay Product Research export, candidate, and label inputs."
    )
    parser.add_argument("--export", required=True)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--labels", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--query", default="")
    parser.add_argument("--target-cards", type=int, default=25)
    parser.add_argument("--min-labeled-rows", type=int, default=50)
    parser.add_argument("--min-label-coverage", type=float, default=0.90)
    parser.add_argument("--min-intake-retention", type=float, default=0.90)
    parser.add_argument("--min-positive-recall", type=float, default=0.80)
    parser.add_argument("--min-negative-label-share", type=float, default=0.20)
    parser.add_argument("--max-review-rate", type=float, default=0.35)
    parser.add_argument("--max-single-card-share", type=float, default=0.20)
    parser.add_argument("--max-sport-share", type=float, default=0.40)
    args = parser.parse_args()

    candidates = json.loads(Path(args.candidates).read_text())
    labels = json.loads(Path(args.labels).read_text())
    report = build_product_research_corpus_proof(
        args.export,
        candidates,
        labels,
        policy=ProofPolicy(
            target_cards=args.target_cards,
            min_labeled_rows=args.min_labeled_rows,
            min_label_coverage=args.min_label_coverage,
            min_intake_retention=args.min_intake_retention,
            min_positive_recall=args.min_positive_recall,
            min_negative_label_share=args.min_negative_label_share,
            max_review_rate=args.max_review_rate,
            max_single_card_share=args.max_single_card_share,
            max_sport_share=args.max_sport_share,
        ),
        query=args.query,
    )
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0 if report["proof_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
