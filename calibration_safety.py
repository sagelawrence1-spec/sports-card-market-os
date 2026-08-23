from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from typing import Iterable


@dataclass(frozen=True)
class CalibrationSafetyPolicy:
    min_mae_improvement_pct: float = 0.0
    min_directional_accuracy_lift: float = 0.0
    min_segment_samples: int = 10
    required_evidence_grades: tuple[str, ...] = ("A", "B")
    required_confidence_bands: tuple[str, ...] = ("high", "medium")
    min_history_checkpoints: int = 3
    min_new_mature_samples_per_checkpoint: int = 5


def _segment_observations(benchmark: dict, family: str, key: str) -> int:
    segment = benchmark.get("segments", {}).get(family, {}).get(key)
    if not isinstance(segment, dict):
        return 0
    try:
        return int(segment.get("observations", 0))
    except (TypeError, ValueError):
        return 0


def _finite_float(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if isfinite(parsed) else None


def assess_calibration_safety(
    benchmark: dict,
    *,
    policy: CalibrationSafetyPolicy | None = None,
) -> dict:
    """Decide whether benchmark evidence is strong enough for human threshold review.

    This gate is intentionally fail-closed. Passing it never authorizes automatic
    threshold changes; it only permits a human calibration review to begin.
    """

    policy = policy or CalibrationSafetyPolicy()
    blockers: list[str] = []
    warnings: list[str] = []

    if not benchmark.get("production_ready", False):
        blockers.append("benchmark_not_production_ready")

    lift = benchmark.get("lift") or {}
    mae_lift_raw = lift.get("mae_improvement_pct")
    direction_lift_raw = lift.get("directional_accuracy_lift")
    mae_lift = _finite_float(mae_lift_raw) if mae_lift_raw is not None else None
    direction_lift = (
        _finite_float(direction_lift_raw) if direction_lift_raw is not None else None
    )

    if mae_lift_raw is None:
        blockers.append("missing_net_mae_lift")
    elif mae_lift is None:
        blockers.append("invalid_net_mae_lift")
    elif mae_lift <= policy.min_mae_improvement_pct:
        blockers.append("non_positive_net_mae_lift")

    if direction_lift_raw is None:
        blockers.append("missing_directional_lift")
    elif direction_lift is None:
        blockers.append("invalid_directional_lift")
    elif direction_lift < policy.min_directional_accuracy_lift:
        blockers.append("negative_directional_lift")

    for grade in policy.required_evidence_grades:
        count = _segment_observations(benchmark, "evidence_grade", grade)
        if count < policy.min_segment_samples:
            blockers.append(f"underpowered_evidence_grade:{grade}")

    for band in policy.required_confidence_bands:
        count = _segment_observations(benchmark, "confidence_band", band)
        if count < policy.min_segment_samples:
            blockers.append(f"underpowered_confidence_band:{band}")

    unknown_evidence = _segment_observations(benchmark, "evidence_grade", "unknown")
    unknown_confidence = _segment_observations(benchmark, "confidence_band", "unknown")
    if unknown_evidence:
        warnings.append("unknown_evidence_grade_present")
    if unknown_confidence:
        warnings.append("unknown_confidence_present")

    blockers = list(dict.fromkeys(blockers))
    warnings = list(dict.fromkeys(warnings))
    review_allowed = not blockers

    return {
        "calibration_review_allowed": review_allowed,
        "automatic_threshold_changes_allowed": False,
        "decision": "human_review_allowed" if review_allowed else "blocked",
        "policy": {
            "min_mae_improvement_pct": policy.min_mae_improvement_pct,
            "min_directional_accuracy_lift": policy.min_directional_accuracy_lift,
            "min_segment_samples": policy.min_segment_samples,
            "required_evidence_grades": list(policy.required_evidence_grades),
            "required_confidence_bands": list(policy.required_confidence_bands),
            "min_history_checkpoints": policy.min_history_checkpoints,
            "min_new_mature_samples_per_checkpoint": policy.min_new_mature_samples_per_checkpoint,
        },
        "blockers": blockers,
        "warnings": warnings,
    }


def _parse_run_date(value: object) -> date | None:
    """Parse an exact ISO date or ISO datetime without accepting trailing garbage."""

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value:
        return None

    raw = value.strip()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        pass

    # Permit real ISO datetime timestamps from persisted/external history, but require
    # the entire string to parse. This prevents values such as ``2026-08-01garbage``
    # from being silently truncated to a valid checkpoint date.
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        return None


def _run_date(run: dict) -> date | None:
    """Resolve one benchmark checkpoint date without allowing metadata disagreement.

    Persisted benchmark runs carry both an outer ``evaluated_at`` field and the
    point-in-time result's ``evaluation_date``. If both are present they must resolve
    to the same calendar date; otherwise history ordering could be manufactured by
    rewriting only the wrapper metadata around an older result packet.
    """

    outer_value = run.get("evaluated_at")
    result_value = (run.get("result") or {}).get("evaluation_date")
    outer_date = _parse_run_date(outer_value) if outer_value else None
    result_date = _parse_run_date(result_value) if result_value else None

    if outer_value and outer_date is None:
        return None
    if result_value and result_date is None:
        return None
    if outer_date is not None and result_date is not None and outer_date != result_date:
        return None
    return outer_date or result_date


def _mature_count(run: dict) -> int | None:
    value = (run.get("result") or {}).get("mature_observations")
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if raw and raw.isdigit():
            return int(raw)
    return None


def assess_calibration_history(
    runs: Iterable[dict],
    *,
    policy: CalibrationSafetyPolicy | None = None,
    as_of: date | None = None,
) -> dict:
    """Require repeated, newly matured out-of-sample evidence before calibration review.

    A single favorable benchmark snapshot is not enough. The most recent checkpoints
    must each pass the point-in-time safety gate, advance chronologically, and add a
    minimum number of newly matured observations so repeated scoring of the same
    outcomes cannot masquerade as stability. Checkpoints dated after ``as_of`` are
    rejected so future-dated packets cannot manufacture apparent history.
    """

    policy = policy or CalibrationSafetyPolicy()
    cutoff = as_of or date.today()
    blockers: list[str] = []
    rows = list(runs)

    if policy.min_history_checkpoints < 1:
        raise ValueError("min_history_checkpoints must be >= 1")
    if policy.min_new_mature_samples_per_checkpoint < 1:
        raise ValueError("min_new_mature_samples_per_checkpoint must be >= 1")

    parsed: list[tuple[date, int, dict, dict]] = []
    for index, run in enumerate(rows):
        if not isinstance(run, dict) or not isinstance(run.get("result"), dict):
            blockers.append(f"invalid_benchmark_run:{index}")
            continue
        evaluated_at = _run_date(run)
        mature = _mature_count(run)
        if evaluated_at is None:
            blockers.append(f"invalid_evaluation_date:{index}")
            continue
        if evaluated_at > cutoff:
            blockers.append(f"future_evaluation_date:{index}")
            continue
        if mature is None or mature < 0:
            blockers.append(f"invalid_mature_observations:{index}")
            continue
        safety = assess_calibration_safety(run["result"], policy=policy)
        parsed.append((evaluated_at, mature, run, safety))

    if len(parsed) < policy.min_history_checkpoints:
        blockers.append("insufficient_calibration_checkpoints")

    if parsed:
        for previous, current in zip(parsed, parsed[1:]):
            if current[0] <= previous[0]:
                blockers.append("non_chronological_calibration_history")
                break

        window = parsed[-policy.min_history_checkpoints :]
        for evaluated_at, _mature, _run, safety in window:
            if not safety["calibration_review_allowed"]:
                blockers.append(f"unsafe_checkpoint:{evaluated_at.isoformat()}")

        for previous, current in zip(window, window[1:]):
            new_mature = current[1] - previous[1]
            if new_mature < policy.min_new_mature_samples_per_checkpoint:
                blockers.append(
                    f"insufficient_new_mature_samples:{current[0].isoformat()}"
                )

    blockers = list(dict.fromkeys(blockers))
    review_allowed = not blockers
    latest_date = parsed[-1][0].isoformat() if parsed else None
    latest_mature = parsed[-1][1] if parsed else None

    return {
        "schema": "calibration-history.v1",
        "calibration_review_allowed": review_allowed,
        "automatic_threshold_changes_allowed": False,
        "decision": "human_review_allowed" if review_allowed else "blocked",
        "checkpoints_seen": len(parsed),
        "required_checkpoints": policy.min_history_checkpoints,
        "min_new_mature_samples_per_checkpoint": policy.min_new_mature_samples_per_checkpoint,
        "latest_evaluation_date": latest_date,
        "latest_mature_observations": latest_mature,
        "blockers": blockers,
    }
