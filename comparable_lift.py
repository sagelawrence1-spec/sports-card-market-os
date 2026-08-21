from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import mean
from typing import Iterable


SCHEMA = "comparable-lift.v1"


@dataclass(frozen=True)
class ComparableBenchmarkObservation:
    card_id: str
    family: str
    as_of_date: date
    horizon_days: int
    current_price: float
    baseline_estimate: float
    comparable_estimate: float
    realized_price: float | None = None
    realized_at: date | None = None
    exit_fee_rate: float = 0.0
    liquidity_haircut_rate: float = 0.0

    @property
    def horizon_end(self) -> date:
        return self.as_of_date + timedelta(days=self.horizon_days)

    @property
    def net_realized_price(self) -> float | None:
        if self.realized_price is None:
            return None
        fee = min(max(float(self.exit_fee_rate), 0.0), 1.0)
        liquidity = min(max(float(self.liquidity_haircut_rate), 0.0), 1.0)
        return float(self.realized_price) * (1.0 - fee) * (1.0 - liquidity)

    def is_mature_at(self, evaluation_date: date) -> bool:
        return (
            self.realized_price is not None
            and self.realized_at is not None
            and self.horizon_end <= evaluation_date
            and self.realized_at >= self.horizon_end
            and self.realized_at <= evaluation_date
        )


@dataclass(frozen=True)
class ComparableLiftPolicy:
    min_mature_samples: int = 20
    min_family_samples: int = 5
    min_mae_improvement_pct: float = 0.05
    min_directional_lift: float = 0.0
    min_family_mae_improvement_pct: float = 0.0
    min_family_directional_lift: float = 0.0

    def validate(self) -> None:
        if self.min_mature_samples < 1:
            raise ValueError("min_mature_samples must be >= 1")
        if self.min_family_samples < 1:
            raise ValueError("min_family_samples must be >= 1")
        if not -1.0 <= self.min_mae_improvement_pct <= 1.0:
            raise ValueError("min_mae_improvement_pct must be between -1 and 1")
        if not -1.0 <= self.min_directional_lift <= 1.0:
            raise ValueError("min_directional_lift must be between -1 and 1")
        if not -1.0 <= self.min_family_mae_improvement_pct <= 1.0:
            raise ValueError("min_family_mae_improvement_pct must be between -1 and 1")
        if not -1.0 <= self.min_family_directional_lift <= 1.0:
            raise ValueError("min_family_directional_lift must be between -1 and 1")


def _direction(value: float, reference: float, tolerance: float = 1e-9) -> int:
    delta = value - reference
    if abs(delta) <= tolerance:
        return 0
    return 1 if delta > 0 else -1


def _metrics(rows: list[ComparableBenchmarkObservation]) -> dict:
    if not rows:
        return {
            "observations": 0,
            "baseline_mae": None,
            "comparable_mae": None,
            "mae_improvement_pct": None,
            "baseline_directional_accuracy": None,
            "comparable_directional_accuracy": None,
            "directional_lift": None,
        }

    targets = [float(row.net_realized_price) for row in rows]
    baseline_mae = mean(abs(row.baseline_estimate - target) for row, target in zip(rows, targets))
    comparable_mae = mean(abs(row.comparable_estimate - target) for row, target in zip(rows, targets))
    mae_improvement = None if baseline_mae == 0 else (baseline_mae - comparable_mae) / baseline_mae

    baseline_hits = 0
    comparable_hits = 0
    for row, target in zip(rows, targets):
        realized_direction = _direction(target, row.current_price)
        baseline_hits += _direction(row.baseline_estimate, row.current_price) == realized_direction
        comparable_hits += _direction(row.comparable_estimate, row.current_price) == realized_direction
    baseline_direction = baseline_hits / len(rows)
    comparable_direction = comparable_hits / len(rows)

    return {
        "observations": len(rows),
        "baseline_mae": baseline_mae,
        "comparable_mae": comparable_mae,
        "mae_improvement_pct": mae_improvement,
        "baseline_directional_accuracy": baseline_direction,
        "comparable_directional_accuracy": comparable_direction,
        "directional_lift": comparable_direction - baseline_direction,
    }


def evaluate_comparable_lift(
    observations: Iterable[ComparableBenchmarkObservation],
    *,
    evaluation_date: date,
    policy: ComparableLiftPolicy | None = None,
) -> dict:
    """Measure hierarchy-comparable lift without allowing immature outcomes to leak in.

    Comparable intelligence cannot graduate from aggregate wins alone. Every represented
    family must clear a mature sample floor and, once sampled, must not regress versus
    the simple sold-comp baseline on MAE or directional accuracy beyond policy.
    """
    policy = policy or ComparableLiftPolicy()
    policy.validate()
    rows = list(observations)
    mature = [row for row in rows if row.is_mature_at(evaluation_date)]
    immature = [row for row in rows if not row.is_mature_at(evaluation_date)]

    families: dict[str, list[ComparableBenchmarkObservation]] = {}
    for row in mature:
        family = str(row.family or "").strip().lower()
        if not family:
            raise ValueError("family is required for mature comparable observations")
        families.setdefault(family, []).append(row)

    overall = _metrics(mature)
    family_metrics = {family: _metrics(families[family]) for family in sorted(families)}

    blockers: list[str] = []
    if len(mature) < policy.min_mature_samples:
        blockers.append("insufficient_mature_samples")
    thin_families = sorted(
        family for family, family_rows in families.items() if len(family_rows) < policy.min_family_samples
    )
    if thin_families:
        blockers.append("insufficient_family_samples")

    improvement = overall["mae_improvement_pct"]
    if improvement is None or improvement < policy.min_mae_improvement_pct:
        blockers.append("insufficient_mae_lift")
    directional_lift = overall["directional_lift"]
    if directional_lift is None or directional_lift < policy.min_directional_lift:
        blockers.append("directional_accuracy_regression")

    sampled_families = [
        family for family in sorted(families) if len(families[family]) >= policy.min_family_samples
    ]
    mae_regressing_families = [
        family
        for family in sampled_families
        if family_metrics[family]["mae_improvement_pct"] is None
        or family_metrics[family]["mae_improvement_pct"] < policy.min_family_mae_improvement_pct
    ]
    directional_regressing_families = [
        family
        for family in sampled_families
        if family_metrics[family]["directional_lift"] is None
        or family_metrics[family]["directional_lift"] < policy.min_family_directional_lift
    ]
    if mae_regressing_families:
        blockers.append("family_mae_regression")
    if directional_regressing_families:
        blockers.append("family_directional_regression")

    return {
        "schema": SCHEMA,
        "evaluation_date": evaluation_date.isoformat(),
        "total_observations": len(rows),
        "mature_observations": len(mature),
        "immature_observations": len(immature),
        "outcome_basis": "net_realized_after_exit_fees_and_liquidity_haircut",
        "policy": {
            "min_mature_samples": policy.min_mature_samples,
            "min_family_samples": policy.min_family_samples,
            "min_mae_improvement_pct": policy.min_mae_improvement_pct,
            "min_directional_lift": policy.min_directional_lift,
            "min_family_mae_improvement_pct": policy.min_family_mae_improvement_pct,
            "min_family_directional_lift": policy.min_family_directional_lift,
        },
        "overall": overall,
        "families": family_metrics,
        "thin_families": thin_families,
        "mae_regressing_families": mae_regressing_families,
        "directional_regressing_families": directional_regressing_families,
        "production_ready": not blockers,
        "blockers": blockers,
    }
