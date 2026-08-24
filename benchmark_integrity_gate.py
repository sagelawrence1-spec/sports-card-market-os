from __future__ import annotations

from collections import Counter
from collections.abc import Iterable as IterableABC, Mapping
from datetime import date, datetime
from math import isfinite
from typing import Iterable

from benchmark_outcome_integrity import assess_benchmark_outcome_integrity
from intelligence_benchmark import BenchmarkObservation, evaluate_intelligence_vs_baseline


def _valid_date(value: object) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


def _valid_horizon(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _valid_min_mature_samples(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _canonical_card_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    card_id = value.strip()
    return card_id or None


def _valid_positive_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(float(value))
        and float(value) > 0
    )


def _valid_unit_rate(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    )


def _valid_optional_confidence(value: object) -> bool:
    return value is None or _valid_unit_rate(value)


def _valid_decision(row: BenchmarkObservation) -> bool:
    return (
        _canonical_card_id(row.card_id) is not None
        and _valid_date(row.as_of_date)
        and _valid_horizon(row.horizon_days)
    )


def _valid_decision_values(row: BenchmarkObservation) -> bool:
    return (
        _valid_positive_number(row.current_price)
        and _valid_positive_number(row.baseline_estimate)
        and _valid_positive_number(row.intelligence_estimate)
        and _valid_unit_rate(row.exit_fee_rate)
        and _valid_unit_rate(row.liquidity_haircut_rate)
        and _valid_optional_confidence(row.confidence)
    )


def _decision_key(row: BenchmarkObservation) -> tuple[str, date, int]:
    card_id = _canonical_card_id(row.card_id)
    if card_id is None or not _valid_date(row.as_of_date) or not _valid_horizon(row.horizon_days):
        raise ValueError("benchmark decision key requires valid card/date/horizon provenance")
    return (card_id, row.as_of_date, row.horizon_days)


def _materialize_observations(value: object) -> tuple[list[BenchmarkObservation], bool, int]:
    """Return valid observation objects plus container/member integrity metadata.

    Mappings and text are technically iterable but are never valid benchmark packet
    containers. Invalid members are excluded before attribute access so malformed
    persisted/replay packets fail closed instead of crashing the integrity gate.
    """

    if (
        value is None
        or isinstance(value, (str, bytes, bytearray, Mapping))
        or not isinstance(value, IterableABC)
    ):
        return [], True, 0

    raw_rows = list(value)
    rows = [row for row in raw_rows if isinstance(row, BenchmarkObservation)]
    return rows, False, len(raw_rows) - len(rows)


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
    Decisions made after the evaluation cutoff are excluded entirely so a replay
    cannot score or count information that did not exist at that point in time.
    Malformed decision provenance or numeric decision-time inputs are excluded before
    outcome/scoring math so corrupt packets fail closed instead of poisoning metrics.
    The mature-sample readiness threshold is itself validated so negative or boolean
    policy values cannot silently weaken the production gate. The observation packet
    container and each member are also validated before attribute access so corrupt
    replay inputs cannot crash or masquerade as empty/valid benchmark evidence.
    """

    cutoff = evaluation_date or date.today()
    if not _valid_date(cutoff):
        raise ValueError("benchmark integrity evaluation_date must be a date")

    invalid_sample_gate = not _valid_min_mature_samples(min_mature_samples)
    effective_min_mature_samples = min_mature_samples if not invalid_sample_gate else 20

    rows, invalid_observation_container, invalid_observation_members = _materialize_observations(observations)
    invalid_decision_ids = sorted(
        {
            _canonical_card_id(row.card_id) or "<invalid-card-id>"
            for row in rows
            if not _valid_decision(row)
        }
    )
    provenance_valid_rows = [row for row in rows if _valid_decision(row)]

    invalid_value_ids = sorted(
        {
            _canonical_card_id(row.card_id)
            for row in provenance_valid_rows
            if not _valid_decision_values(row)
        }
    )
    value_valid_rows = [row for row in provenance_valid_rows if _valid_decision_values(row)]

    future_decision_ids = sorted(
        {
            _canonical_card_id(row.card_id)
            for row in value_valid_rows
            if row.as_of_date > cutoff
        }
    )
    eligible_rows = [row for row in value_valid_rows if row.as_of_date <= cutoff]

    integrity = assess_benchmark_outcome_integrity(eligible_rows, evaluation_date=cutoff)

    decision_counts = Counter(_decision_key(row) for row in eligible_rows)
    duplicate_keys = {key for key, count in decision_counts.items() if count > 1}
    duplicate_ids = sorted({key[0] for key in duplicate_keys})

    invalid_ids = set(integrity.invalid_outcome_card_ids)
    scoring_rows = [
        row
        for row in eligible_rows
        if _canonical_card_id(row.card_id) not in invalid_ids
        and _decision_key(row) not in duplicate_keys
    ]
    result = evaluate_intelligence_vs_baseline(
        scoring_rows,
        evaluation_date=cutoff,
        min_mature_samples=effective_min_mature_samples,
    )

    blockers = list(result.get("blockers") or [])
    for blocker in integrity.blockers:
        if blocker not in blockers:
            blockers.append(blocker)
    if invalid_observation_container and "invalid_benchmark_observation_container" not in blockers:
        blockers.append("invalid_benchmark_observation_container")
    if invalid_observation_members and "invalid_benchmark_observation_member" not in blockers:
        blockers.append("invalid_benchmark_observation_member")
    if invalid_decision_ids and "invalid_benchmark_decision_provenance" not in blockers:
        blockers.append("invalid_benchmark_decision_provenance")
    if invalid_value_ids and "invalid_benchmark_decision_values" not in blockers:
        blockers.append("invalid_benchmark_decision_values")
    if duplicate_ids and "duplicate_benchmark_decision_packet" not in blockers:
        blockers.append("duplicate_benchmark_decision_packet")
    if future_decision_ids and "benchmark_decision_after_evaluation_cutoff" not in blockers:
        blockers.append("benchmark_decision_after_evaluation_cutoff")
    if invalid_sample_gate and "invalid_benchmark_min_mature_samples" not in blockers:
        blockers.append("invalid_benchmark_min_mature_samples")

    total_observations = len(rows) + invalid_observation_members
    return {
        **result,
        "total_observations": total_observations,
        "production_ready": not blockers,
        "blockers": blockers,
        "outcome_integrity": {
            "partial_outcome_card_ids": list(integrity.partial_outcome_card_ids),
            "early_outcome_card_ids": list(integrity.early_outcome_card_ids),
            "overdue_unsettled_card_ids": list(integrity.overdue_unsettled_card_ids),
            "invalid_outcome_card_ids": list(integrity.invalid_outcome_card_ids),
            "invalid_decision_card_ids": invalid_decision_ids,
            "invalid_decision_value_card_ids": invalid_value_ids,
            "duplicate_decision_card_ids": duplicate_ids,
            "future_decision_card_ids": future_decision_ids,
            "invalid_observation_members": invalid_observation_members,
        },
    }
