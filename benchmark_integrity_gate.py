from __future__ import annotations

from datetime import date
from typing import Iterable

from benchmark_outcome_integrity import assess_benchmark_outcome_integrity
from intelligence_benchmark import BenchmarkObservation, evaluate_intelligence_vs_baseline


def evaluate_benchmark_with_integrity(
    observations: Iterable[BenchmarkObservation],
    *,
    evaluation_date: date | None = None,
    min_mature_samples: int = 20,
) -> dict:
    """Evaluate benchmark lift with outcome provenance blockers enforced.

    The base benchmark evaluator owns scoring math. This gate owns whether the
    underlying outcome packet is safe to score for production-readiness purposes.
    """

    cutoff = evaluation_date or date.today()
    rows = list(observations)
    integrity = assess_benchmark_outcome_integrity(rows, evaluation_date=cutoff)
    invalid_ids = set(integrity.invalid_outcome_card_ids)
    scoring_rows = [
        row
        for row in rows
        if not (isinstance(row.card_id, str) and row.card_id.strip() in invalid_ids)
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
        },
    }
