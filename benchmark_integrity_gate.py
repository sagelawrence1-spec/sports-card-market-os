from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Iterable

from benchmark_outcome_integrity import assess_benchmark_outcome_integrity
from intelligence_benchmark import BenchmarkObservation, evaluate_intelligence_vs_baseline


def _decision_key(row: BenchmarkObservation) -> tuple[str, date, int]:
    card_id = row.card_id.strip()
    return (card_id, row.as_of_date, row.horizon_days)


def evaluate_benchmark_with_integrity(
    observations: Iterable[BenchmarkObservation],
    *,
    evaluation_date: date | None = None,
    min_mature_samples: int = 20,
) -> dict:
    """Evaluate benchmark lift with outcome and decision-packet integrity enforced.

    The base benchmark evaluator owns scoring math. This gate owns whether the
    underlying benchmark packet is safe to score for production-readiness purposes.
    A card/as-of/horizon decision may appear only once; duplicate packets would
    otherwise double-weight one historical decision and inflate sample counts.
    """

    cutoff = evaluation_date or date.today()
    rows = list(observations)
    integrity = assess_benchmark_outcome_integrity(rows, evaluation_date=cutoff)

    decision_counts = Counter(_decision_key(row) for row in rows)
    duplicate_keys = {key for key, count in decision_counts.items() if count > 1}
    duplicate_ids = sorted({key[0] for key in duplicate_keys})

    invalid_ids = set(integrity.invalid_outcome_card_ids)
    scoring_rows = [
        row
        for row in rows
        if not (
            isinstance(row.card_id, str)
            and (
                row.card_id.strip() in invalid_ids
                or _decision_key(row) in duplicate_keys
            )
        )
    ]
    result = evaluate_intelligence_vs_baseline(
        scoring_rows,
        evaluation_date=cutoff,
        min_mature_samples=min_mature_samples,
    )

    blockers = list(result.get("blockers") or [])
    for blocker in integrity.blockers:
        if blocker not in blockers:
            blockers.append(blocker)
    if duplicate_ids and "duplicate_benchmark_decision_packet" not in blockers:
        blockers.append("duplicate_benchmark_decision_packet")

    return {
        **result,
        "total_observations": len(rows),
        "production_ready": not blockers,
        "blockers": blockers,
        "outcome_integrity": {
            "partial_outcome_card_ids": list(integrity.partial_outcome_card_ids),
            "early_outcome_card_ids": list(integrity.early_outcome_card_ids),
            "overdue_unsettled_card_ids": list(integrity.overdue_unsettled_card_ids),
            "invalid_outcome_card_ids": list(integrity.invalid_outcome_card_ids),
            "duplicate_decision_card_ids": duplicate_ids,
        },
    }
