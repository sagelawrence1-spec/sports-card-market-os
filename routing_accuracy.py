from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any


SCHEMA = r'''
CREATE TABLE IF NOT EXISTS routing_ground_truth(
  evidence_id TEXT NOT NULL,
  reviewer_id TEXT NOT NULL,
  expected_card_id TEXT,
  is_relevant INTEGER NOT NULL CHECK(is_relevant IN (0,1)),
  labeled_at TEXT DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(evidence_id, reviewer_id)
);
CREATE INDEX IF NOT EXISTS idx_routing_ground_truth_evidence
  ON routing_ground_truth(evidence_id);
'''


@dataclass(frozen=True)
class RoutingAuditPolicy:
    min_labeled_rows: int = 50
    min_distinct_relevant_cards: int = 25
    max_single_card_share: float = 0.20
    min_auto_accept_precision: float = 0.99
    max_review_rate: float = 0.35
    max_false_accepts: int = 0

    def __post_init__(self) -> None:
        if self.min_labeled_rows < 1:
            raise ValueError("min_labeled_rows must be positive")
        if self.min_distinct_relevant_cards < 1:
            raise ValueError("min_distinct_relevant_cards must be positive")
        if not 0 < self.max_single_card_share <= 1:
            raise ValueError("max_single_card_share must be in (0,1]")
        if not 0 <= self.min_auto_accept_precision <= 1:
            raise ValueError("min_auto_accept_precision must be between 0 and 1")
        if not 0 <= self.max_review_rate <= 1:
            raise ValueError("max_review_rate must be between 0 and 1")
        if self.max_false_accepts < 0:
            raise ValueError("max_false_accepts cannot be negative")


class RoutingAccuracyStore:
    def __init__(self, database_path: str):
        self.database_path = str(database_path)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def _connect(self):
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def label(
        self,
        evidence_id: str,
        *,
        reviewer_id: str,
        expected_card_id: str | None,
        is_relevant: bool,
    ) -> None:
        evidence_id = str(evidence_id).strip()
        reviewer_id = str(reviewer_id).strip()
        expected = str(expected_card_id).strip() if expected_card_id is not None else None
        if not evidence_id or not reviewer_id:
            raise ValueError("evidence_id and reviewer_id are required")
        if is_relevant and not expected:
            raise ValueError("relevant evidence requires expected_card_id")
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM source_evidence WHERE evidence_id=?",
                (evidence_id,),
            ).fetchone()
            if exists is None:
                raise KeyError(evidence_id)
            conn.execute(
                '''INSERT INTO routing_ground_truth(
                  evidence_id,reviewer_id,expected_card_id,is_relevant,labeled_at)
                  VALUES(?,?,?,?,CURRENT_TIMESTAMP)
                  ON CONFLICT(evidence_id,reviewer_id) DO UPDATE SET
                    expected_card_id=excluded.expected_card_id,
                    is_relevant=excluded.is_relevant,
                    labeled_at=CURRENT_TIMESTAMP''',
                (evidence_id, reviewer_id, expected, 1 if is_relevant else 0),
            )

    def consensus_labels(self, min_reviewers: int = 1) -> list[sqlite3.Row]:
        if min_reviewers < 1:
            raise ValueError("min_reviewers must be positive")
        with self._connect() as conn:
            return conn.execute(
                '''WITH votes AS (
                     SELECT evidence_id,
                            COUNT(*) AS reviewer_count,
                            COUNT(DISTINCT COALESCE(expected_card_id,'__irrelevant__') || ':' || is_relevant) AS vote_shapes,
                            MAX(expected_card_id) AS expected_card_id,
                            MAX(is_relevant) AS is_relevant
                     FROM routing_ground_truth
                     GROUP BY evidence_id
                   )
                   SELECT e.evidence_id,e.card_id,e.match_status,e.match_reason,
                          v.expected_card_id,v.is_relevant,v.reviewer_count
                   FROM votes v
                   JOIN source_evidence e ON e.evidence_id=v.evidence_id
                   WHERE v.reviewer_count>=? AND v.vote_shapes=1''',
                (min_reviewers,),
            ).fetchall()


def routing_accuracy_summary(
    database_path: str,
    *,
    policy: RoutingAuditPolicy | None = None,
    min_reviewers: int = 1,
) -> dict[str, Any]:
    policy = policy or RoutingAuditPolicy()
    labels = RoutingAccuracyStore(database_path).consensus_labels(min_reviewers=min_reviewers)

    total = len(labels)
    auto_accepts = [row for row in labels if row["match_status"] == "accepted"]
    reviews = [row for row in labels if row["match_status"] == "review"]
    rejects = [row for row in labels if row["match_status"] == "rejected"]

    def correct(row: sqlite3.Row) -> bool:
        if not row["is_relevant"]:
            return row["match_status"] == "rejected"
        return str(row["card_id"] or "") == str(row["expected_card_id"] or "")

    false_accepts = [row for row in auto_accepts if not correct(row)]
    correct_auto_accepts = len(auto_accepts) - len(false_accepts)
    auto_precision = (
        correct_auto_accepts / len(auto_accepts) if auto_accepts else None
    )

    relevant = [row for row in labels if row["is_relevant"]]
    relevant_captured = [
        row for row in relevant
        if row["match_status"] in {"accepted", "review"}
        and str(row["card_id"] or "") == str(row["expected_card_id"] or "")
    ]
    positive_recall = len(relevant_captured) / len(relevant) if relevant else None
    review_rate = len(reviews) / total if total else None
    false_rejects = [row for row in rejects if row["is_relevant"]]

    relevant_card_counts = Counter(
        str(row["expected_card_id"])
        for row in relevant
        if row["expected_card_id"] is not None
    )
    distinct_relevant_cards = len(relevant_card_counts)
    largest_card_rows = max(relevant_card_counts.values(), default=0)
    largest_card_share = (
        largest_card_rows / len(relevant) if relevant else None
    )

    blockers: list[str] = []
    if total < policy.min_labeled_rows:
        blockers.append("labeled_sample_too_small")
    if distinct_relevant_cards < policy.min_distinct_relevant_cards:
        blockers.append("relevant_card_coverage_too_narrow")
    if (
        largest_card_share is not None
        and largest_card_share > policy.max_single_card_share
    ):
        blockers.append("single_card_overrepresented")
    if len(false_accepts) > policy.max_false_accepts:
        blockers.append("false_accepts_observed")
    if auto_precision is not None and auto_precision < policy.min_auto_accept_precision:
        blockers.append("auto_accept_precision_below_floor")
    if review_rate is not None and review_rate > policy.max_review_rate:
        blockers.append("review_rate_above_ceiling")

    return {
        "production_ready": not blockers,
        "blockers": blockers,
        "labeled_rows": total,
        "distinct_relevant_cards": distinct_relevant_cards,
        "largest_card_rows": largest_card_rows,
        "largest_card_share": largest_card_share,
        "auto_accepts": len(auto_accepts),
        "false_accepts": len(false_accepts),
        "auto_accept_precision": auto_precision,
        "review_rows": len(reviews),
        "review_rate": review_rate,
        "rejected_rows": len(rejects),
        "false_rejects": len(false_rejects),
        "positive_recall": positive_recall,
    }
