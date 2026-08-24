from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Protocol


class BenchmarkOutcomeLike(Protocol):
    card_id: str
    realized_price: float | None
    realized_at: date | None

    @property
    def horizon_end(self) -> date: ...


@dataclass(frozen=True)
class BenchmarkOutcomeIntegrity:
    partial_outcome_card_ids: tuple[str, ...]
    early_outcome_card_ids: tuple[str, ...]
    overdue_unsettled_card_ids: tuple[str, ...]

    @property
    def blockers(self) -> tuple[str, ...]:
        blockers: list[str] = []
        if self.partial_outcome_card_ids:
            blockers.append("partial_realized_outcome_provenance")
        if self.early_outcome_card_ids:
            blockers.append("realized_outcome_before_horizon")
        if self.overdue_unsettled_card_ids:
            blockers.append("overdue_unsettled_forward_outcomes")
        return tuple(blockers)

    @property
    def production_safe(self) -> bool:
        return not self.blockers


def _canonical_card_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("benchmark outcome integrity requires card_id to be text")
    card_id = value.strip()
    if not card_id:
        raise ValueError("benchmark outcome integrity requires a non-blank card_id")
    return card_id


def assess_benchmark_outcome_integrity(
    observations: Iterable[BenchmarkOutcomeLike], *, evaluation_date: date
) -> BenchmarkOutcomeIntegrity:
    """Classify outcome provenance before benchmark rows enter maturity scoring.

    A completed forward outcome needs both price and observation date, and its
    observation date cannot precede the benchmark horizon. Once the horizon has
    expired, a row with no outcome at all is overdue rather than merely immature.
    Future-horizon rows with no outcome remain legitimately immature.
    """

    partial: set[str] = set()
    early: set[str] = set()
    overdue: set[str] = set()

    for row in observations:
        card_id = _canonical_card_id(row.card_id)

        has_price = row.realized_price is not None
        has_date = row.realized_at is not None

        if has_price != has_date:
            partial.add(card_id)
            continue

        if has_price and has_date:
            assert row.realized_at is not None
            if row.realized_at < row.horizon_end:
                early.add(card_id)
            continue

        if row.horizon_end <= evaluation_date:
            overdue.add(card_id)

    return BenchmarkOutcomeIntegrity(
        partial_outcome_card_ids=tuple(sorted(partial)),
        early_outcome_card_ids=tuple(sorted(early)),
        overdue_unsettled_card_ids=tuple(sorted(overdue)),
    )
