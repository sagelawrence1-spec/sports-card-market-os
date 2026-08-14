"""One-command real-corpus proof packet for routing validation."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from corpus_intake import CorpusIntakePolicy, sanitize_product_research_rows
from routing_audit import audit_routing, labels_from_rows
from routing_corpus_manifest import CorpusManifestPolicy, build_routing_corpus_manifest


@dataclass(frozen=True)
class ProofPolicy:
    target_cards: int = 25
    min_labeled_rows: int = 50
    max_review_rate: float = 0.35
    max_single_card_share: float = 0.20
    max_sport_share: float = 0.40

    def __post_init__(self) -> None:
        if self.target_cards < 1 or self.min_labeled_rows < 1:
            raise ValueError("proof sample floors must be positive")
        if not 0 <= self.max_review_rate <= 1:
            raise ValueError("max_review_rate must be between 0 and 1")
        if not 0 < self.max_single_card_share <= 1:
            raise ValueError("max_single_card_share must be in (0,1]")
        if not 0 < self.max_sport_share <= 1:
            raise ValueError("max_sport_share must be in (0,1]")


def load_delimited_export(path: str | Path) -> list[dict[str, str]]:
    text = Path(path).read_text(encoding="utf-8-sig")
    if not text.strip():
        return []
    header = text.splitlines()[0]
    if "\t" in header:
        delimiter = "\t"
    elif ";" in header and "," not in header:
        delimiter = ";"
    else:
        delimiter = ","
    return [dict(row) for row in csv.DictReader(text.splitlines(), delimiter=delimiter)]


def build_corpus_proof_report(
    raw_rows: Iterable[Mapping[str, Any]],
    candidates: list[Mapping[str, Any]],
    label_rows: list[Mapping[str, Any]],
    *,
    policy: ProofPolicy | None = None,
    seed: str = "routing-corpus-v1",
) -> dict[str, Any]:
    policy = policy or ProofPolicy()

    intake = sanitize_product_research_rows(
        raw_rows,
        policy=CorpusIntakePolicy(require_usd=True, require_item_id=False),
    )
    manifest = build_routing_corpus_manifest(
        candidates,
        policy=CorpusManifestPolicy(
            target_size=policy.target_cards,
            max_sport_share=policy.max_sport_share,
        ),
        seed=seed,
    )

    accepted_ids = {
        str(row.get("item_id") or row["fingerprint"])
        for row in intake["accepted"]
    }
    selected_cards = {row["card_id"] for row in manifest["cards"]}

    scoped_labels: list[Mapping[str, Any]] = []
    orphan_labels = 0
    off_manifest_labels = 0
    for row in label_rows:
        evidence_id = str(row.get("evidence_id") or "")
        if evidence_id not in accepted_ids:
            orphan_labels += 1
            continue
        expected_card_id = row.get("expected_card_id")
        if expected_card_id is not None and str(expected_card_id) not in selected_cards:
            off_manifest_labels += 1
            continue
        scoped_labels.append(row)

    routing = audit_routing(
        labels_from_rows(scoped_labels),
        min_labeled_rows=policy.min_labeled_rows,
    )

    relevant = [
        row
        for row in scoped_labels
        if row.get("expected_status") == "accepted" and row.get("expected_card_id")
    ]
    counts: dict[str, int] = {}
    for row in relevant:
        card_id = str(row["expected_card_id"])
        counts[card_id] = counts.get(card_id, 0) + 1

    distinct_labeled_cards = len(counts)
    largest_card_rows = max(counts.values(), default=0)
    largest_card_share = largest_card_rows / len(relevant) if relevant else None

    blockers: list[str] = []
    if not intake["ready"]:
        blockers.extend(f"intake:{value}" for value in intake["blockers"])
    if orphan_labels:
        blockers.append("labels_outside_sanitized_corpus")
    if off_manifest_labels:
        blockers.append("labels_outside_selected_manifest")
    if distinct_labeled_cards < policy.target_cards:
        blockers.append("selected_card_coverage_incomplete")
    if largest_card_share is not None and largest_card_share > policy.max_single_card_share:
        blockers.append("single_card_overrepresented")
    if routing["review_rate"] is not None and routing["review_rate"] > policy.max_review_rate:
        blockers.append("review_rate_above_ceiling")
    blockers.extend(f"routing:{value}" for value in routing["blockers"])

    return {
        "proof_version": "routing-proof.v1",
        "proof_ready": not blockers,
        "blockers": blockers,
        "corpus_sha256": intake["corpus_sha256"],
        "intake": {
            "input_rows": intake["input_rows"],
            "accepted_rows": intake["accepted_rows"],
            "rejected_rows": intake["rejected_rows"],
            "duplicates": intake["duplicates"],
        },
        "manifest": manifest,
        "labels": {
            "provided": len(label_rows),
            "scoped": len(scoped_labels),
            "orphan": orphan_labels,
            "off_manifest": off_manifest_labels,
            "distinct_labeled_cards": distinct_labeled_cards,
            "largest_card_share": largest_card_share,
        },
        "routing": routing,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a real eBay routing proof packet.")
    parser.add_argument("--export", required=True)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--labels", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--target-cards", type=int, default=25)
    parser.add_argument("--min-labeled-rows", type=int, default=50)
    args = parser.parse_args()

    candidates = json.loads(Path(args.candidates).read_text())
    labels = json.loads(Path(args.labels).read_text())
    report = build_corpus_proof_report(
        load_delimited_export(args.export),
        candidates,
        labels,
        policy=ProofPolicy(
            target_cards=args.target_cards,
            min_labeled_rows=args.min_labeled_rows,
        ),
    )
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0 if report["proof_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
