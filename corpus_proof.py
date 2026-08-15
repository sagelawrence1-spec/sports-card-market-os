"""One-command real-corpus proof packet for routing validation."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from corpus_intake import CorpusIntakePolicy, sanitize_product_research_rows
from entity_matcher import MatchDecision, SportsCardEntityMatcher
from routing_audit import audit_routing, labels_from_rows
from routing_corpus_manifest import CorpusManifestPolicy, build_routing_corpus_manifest


@dataclass(frozen=True)
class ProofPolicy:
    target_cards: int = 25
    min_labeled_rows: int = 50
    min_label_coverage: float = 0.90
    min_intake_retention: float = 0.90
    min_positive_recall: float = 0.80
    min_negative_label_share: float | None = None
    max_review_rate: float = 0.35
    max_single_card_share: float = 0.20
    max_sport_share: float = 0.40

    def __post_init__(self) -> None:
        if self.target_cards < 1 or self.min_labeled_rows < 1:
            raise ValueError("proof sample floors must be positive")
        if not 0 <= self.min_label_coverage <= 1:
            raise ValueError("min_label_coverage must be between 0 and 1")
        if not 0 <= self.min_intake_retention <= 1:
            raise ValueError("min_intake_retention must be between 0 and 1")
        if not 0 <= self.min_positive_recall <= 1:
            raise ValueError("min_positive_recall must be between 0 and 1")
        if self.min_negative_label_share is not None and not 0 <= self.min_negative_label_share <= 1:
            raise ValueError("min_negative_label_share must be between 0 and 1")
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


def _prediction_for_title(
    title: str,
    assets: list[Mapping[str, Any]],
    matcher: SportsCardEntityMatcher,
) -> dict[str, Any]:
    """Run the same candidate ranking/ambiguity rule used by live evidence routing."""
    ranked = sorted(
        ((matcher.match(dict(asset), title), asset) for asset in assets),
        key=lambda pair: pair[0].score,
        reverse=True,
    )
    decision, asset = ranked[0]
    if len(ranked) > 1 and decision.accepted and ranked[1][0].score >= decision.score - 3:
        decision = MatchDecision(
            False,
            decision.score,
            "manual_review",
            {
                **decision.diagnostics,
                "ambiguous_candidates": [
                    str(asset["card_id"]),
                    str(ranked[1][1]["card_id"]),
                ],
            },
        )

    status = (
        "accepted"
        if decision.accepted
        else "review"
        if decision.reason == "manual_review"
        else "rejected"
    )
    return {
        "predicted_status": status,
        "predicted_card_id": str(asset["card_id"]),
        "match_score": decision.score,
        "match_reason": decision.reason,
    }


def _generate_predictions(
    accepted_rows: Iterable[Mapping[str, Any]],
    assets: list[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    matcher = SportsCardEntityMatcher()
    predictions: dict[str, dict[str, Any]] = {}
    for row in accepted_rows:
        evidence_id = str(row.get("item_id") or row["fingerprint"])
        predictions[evidence_id] = _prediction_for_title(
            str(row.get("title") or ""),
            assets,
            matcher,
        )
    return predictions


def build_corpus_proof_report(
    raw_rows: Iterable[Mapping[str, Any]],
    candidates: list[Mapping[str, Any]],
    label_rows: list[Mapping[str, Any]],
    *,
    policy: ProofPolicy | None = None,
    seed: str = "routing-corpus-v1",
) -> dict[str, Any]:
    policy = policy or ProofPolicy(min_negative_label_share=0.20)

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
    selected_assets = [
        card for card in candidates if str(card.get("card_id")) in selected_cards
    ]
    predictions = _generate_predictions(intake["accepted"], selected_assets)

    candidate_labels: dict[str, list[dict[str, Any]]] = {}
    orphan_labels = 0
    off_manifest_labels = 0
    caller_predictions_ignored = 0
    for row in label_rows:
        evidence_id = str(row.get("evidence_id") or "")
        if evidence_id not in accepted_ids:
            orphan_labels += 1
            continue
        expected_card_id = row.get("expected_card_id")
        if expected_card_id is not None and str(expected_card_id) not in selected_cards:
            off_manifest_labels += 1
            continue
        if "predicted_status" in row or "predicted_card_id" in row:
            caller_predictions_ignored += 1
        candidate_labels.setdefault(evidence_id, []).append({
            "expected_status": row["expected_status"],
            "expected_card_id": (
                str(expected_card_id) if expected_card_id is not None else None
            ),
        })

    scoped_labels: list[dict[str, Any]] = []
    duplicate_labels = 0
    conflicting_label_ids: list[str] = []
    for evidence_id, rows in candidate_labels.items():
        truths = {
            (row["expected_status"], row["expected_card_id"])
            for row in rows
        }
        duplicate_labels += max(len(rows) - 1, 0)
        if len(truths) != 1:
            conflicting_label_ids.append(evidence_id)
            continue
        expected_status, expected_card_id = next(iter(truths))
        prediction = predictions[evidence_id]
        scoped_labels.append({
            "evidence_id": evidence_id,
            "predicted_status": prediction["predicted_status"],
            "predicted_card_id": prediction["predicted_card_id"],
            "expected_status": expected_status,
            "expected_card_id": expected_card_id,
        })

    routing = audit_routing(
        labels_from_rows(scoped_labels),
        min_labeled_rows=policy.min_labeled_rows,
    )

    unique_labeled_ids = {row["evidence_id"] for row in scoped_labels}
    label_coverage = (
        len(unique_labeled_ids) / len(accepted_ids)
        if accepted_ids
        else None
    )
    intake_retained_rows = intake["accepted_rows"] + intake["duplicates"]
    intake_retention = (
        intake_retained_rows / intake["input_rows"]
        if intake["input_rows"]
        else None
    )

    negative_labels = [
        row for row in scoped_labels if row.get("expected_status") == "rejected"
    ]
    negative_label_share = (
        len(negative_labels) / len(scoped_labels) if scoped_labels else None
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
    if intake_retention is None or intake_retention < policy.min_intake_retention:
        blockers.append("intake_retention_below_floor")
    if orphan_labels:
        blockers.append("labels_outside_sanitized_corpus")
    if off_manifest_labels:
        blockers.append("labels_outside_selected_manifest")
    if conflicting_label_ids:
        blockers.append("conflicting_duplicate_labels")
    if label_coverage is None or label_coverage < policy.min_label_coverage:
        blockers.append("label_coverage_below_floor")
    if (
        policy.min_negative_label_share is not None
        and (
            negative_label_share is None
            or negative_label_share < policy.min_negative_label_share
        )
    ):
        blockers.append("negative_label_share_below_floor")
    if distinct_labeled_cards < policy.target_cards:
        blockers.append("selected_card_coverage_incomplete")
    if largest_card_share is not None and largest_card_share > policy.max_single_card_share:
        blockers.append("single_card_overrepresented")
    if routing["review_rate"] is not None and routing["review_rate"] > policy.max_review_rate:
        blockers.append("review_rate_above_ceiling")
    if (
        routing["positive_recall"] is None
        or routing["positive_recall"] < policy.min_positive_recall
    ):
        blockers.append("positive_recall_below_floor")
    blockers.extend(f"routing:{value}" for value in routing["blockers"])

    return {
        "proof_version": "routing-proof.v6",
        "proof_ready": not blockers,
        "blockers": blockers,
        "corpus_sha256": intake["corpus_sha256"],
        "policy": {
            "target_cards": policy.target_cards,
            "min_labeled_rows": policy.min_labeled_rows,
            "min_label_coverage": policy.min_label_coverage,
            "min_intake_retention": policy.min_intake_retention,
            "min_positive_recall": policy.min_positive_recall,
            "min_negative_label_share": policy.min_negative_label_share,
            "max_review_rate": policy.max_review_rate,
            "max_single_card_share": policy.max_single_card_share,
            "max_sport_share": policy.max_sport_share,
        },
        "intake": {
            "input_rows": intake["input_rows"],
            "accepted_rows": intake["accepted_rows"],
            "rejected_rows": intake["rejected_rows"],
            "duplicates": intake["duplicates"],
            "retained_rows": intake_retained_rows,
            "retention": intake_retention,
        },
        "manifest": manifest,
        "labels": {
            "provided": len(label_rows),
            "scoped": len(scoped_labels),
            "unique_scoped": len(unique_labeled_ids),
            "duplicate_rows_collapsed": duplicate_labels,
            "conflicting_evidence_ids": sorted(conflicting_label_ids),
            "coverage": label_coverage,
            "unlabeled_sanitized_rows": max(len(accepted_ids) - len(unique_labeled_ids), 0),
            "orphan": orphan_labels,
            "off_manifest": off_manifest_labels,
            "distinct_labeled_cards": distinct_labeled_cards,
            "largest_card_share": largest_card_share,
            "negative_rows": len(negative_labels),
            "negative_share": negative_label_share,
            "prediction_source": "current_entity_matcher",
            "caller_predictions_ignored": caller_predictions_ignored,
        },
        "routing": routing,
        "predictions": {
            evidence_id: predictions[evidence_id]
            for evidence_id in sorted(unique_labeled_ids)
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a real eBay routing proof packet.")
    parser.add_argument("--export", required=True)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--labels", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--target-cards", type=int, default=25)
    parser.add_argument("--min-labeled-rows", type=int, default=50)
    parser.add_argument("--min-label-coverage", type=float, default=0.90)
    parser.add_argument("--min-intake-retention", type=float, default=0.90)
    parser.add_argument("--min-positive-recall", type=float, default=0.80)
    parser.add_argument("--min-negative-label-share", type=float, default=0.20)
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
            min_label_coverage=args.min_label_coverage,
            min_intake_retention=args.min_intake_retention,
            min_positive_recall=args.min_positive_recall,
            min_negative_label_share=args.min_negative_label_share,
        ),
    )
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0 if report["proof_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())