from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

VALID_STATUSES = {"accepted", "review", "rejected"}


@dataclass(frozen=True)
class RoutingLabel:
    evidence_id: str
    predicted_status: str
    expected_status: str
    predicted_card_id: str | None = None
    expected_card_id: str | None = None

    def __post_init__(self):
        if self.predicted_status not in VALID_STATUSES:
            raise ValueError(f"invalid predicted_status: {self.predicted_status}")
        if self.expected_status not in VALID_STATUSES:
            raise ValueError(f"invalid expected_status: {self.expected_status}")


def _safe_rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def audit_routing(labels: Iterable[RoutingLabel], min_labeled_rows: int = 50) -> dict:
    rows = list(labels)
    total = len(rows)

    predicted_accepts = [r for r in rows if r.predicted_status == "accepted"]
    expected_accepts = [r for r in rows if r.expected_status == "accepted"]
    predicted_reviews = [r for r in rows if r.predicted_status == "review"]

    true_accepts = 0
    false_accepts = 0
    false_rejects = 0
    review_capture = 0
    wrong_card_accepts = 0

    for row in rows:
        same_card = (
            row.expected_card_id is None
            or row.predicted_card_id == row.expected_card_id
        )
        if row.predicted_status == "accepted":
            if row.expected_status == "accepted" and same_card:
                true_accepts += 1
            else:
                false_accepts += 1
                if row.expected_status == "accepted" and not same_card:
                    wrong_card_accepts += 1
        elif row.predicted_status == "rejected" and row.expected_status == "accepted":
            false_rejects += 1
        elif row.predicted_status == "review" and row.expected_status != "review":
            review_capture += 1

    auto_accept_precision = _safe_rate(true_accepts, len(predicted_accepts))
    positive_recall = _safe_rate(true_accepts, len(expected_accepts))
    review_rate = _safe_rate(len(predicted_reviews), total)
    false_accept_rate = _safe_rate(false_accepts, len(predicted_accepts))

    blockers: list[str] = []
    if total < min_labeled_rows:
        blockers.append("insufficient_labeled_rows")
    if false_accepts > 0:
        blockers.append("observed_false_accepts")
    if auto_accept_precision is not None and auto_accept_precision < 0.99:
        blockers.append("auto_accept_precision_below_99pct")

    return {
        "labeled_rows": total,
        "predicted_accepts": len(predicted_accepts),
        "predicted_reviews": len(predicted_reviews),
        "expected_accepts": len(expected_accepts),
        "true_accepts": true_accepts,
        "false_accepts": false_accepts,
        "wrong_card_accepts": wrong_card_accepts,
        "false_rejects": false_rejects,
        "review_capture": review_capture,
        "auto_accept_precision": auto_accept_precision,
        "positive_recall": positive_recall,
        "review_rate": review_rate,
        "false_accept_rate": false_accept_rate,
        "production_ready": not blockers,
        "blockers": blockers,
    }


def labels_from_rows(rows: Iterable[Mapping]) -> list[RoutingLabel]:
    return [
        RoutingLabel(
            evidence_id=str(row["evidence_id"]),
            predicted_status=str(row["predicted_status"]),
            expected_status=str(row["expected_status"]),
            predicted_card_id=row.get("predicted_card_id"),
            expected_card_id=row.get("expected_card_id"),
        )
        for row in rows
    ]
