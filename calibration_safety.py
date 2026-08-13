from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CalibrationSafetyPolicy:
    min_mae_improvement_pct: float = 0.0
    min_directional_accuracy_lift: float = 0.0
    min_segment_samples: int = 10
    required_evidence_grades: tuple[str, ...] = ("A", "B")
    required_confidence_bands: tuple[str, ...] = ("high", "medium")


def _segment_observations(benchmark: dict, family: str, key: str) -> int:
    segment = benchmark.get("segments", {}).get(family, {}).get(key)
    if not isinstance(segment, dict):
        return 0
    try:
        return int(segment.get("observations", 0))
    except (TypeError, ValueError):
        return 0


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
    mae_lift = lift.get("mae_improvement_pct")
    direction_lift = lift.get("directional_accuracy_lift")

    if mae_lift is None:
        blockers.append("missing_net_mae_lift")
    elif float(mae_lift) <= policy.min_mae_improvement_pct:
        blockers.append("non_positive_net_mae_lift")

    if direction_lift is None:
        blockers.append("missing_directional_lift")
    elif float(direction_lift) < policy.min_directional_accuracy_lift:
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
        },
        "blockers": blockers,
        "warnings": warnings,
    }
