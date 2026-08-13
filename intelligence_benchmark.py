from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import mean
from typing import Iterable


@dataclass(frozen=True)
class BenchmarkObservation:
    card_id: str
    as_of_date: date
    horizon_days: int
    current_price: float
    baseline_estimate: float
    intelligence_estimate: float
    realized_price: float | None = None
    realized_at: date | None = None
    evidence_grade: str | None = None
    confidence: float | None = None

    @property
    def horizon_end(self) -> date:
        return self.as_of_date + timedelta(days=self.horizon_days)

    @property
    def is_mature(self) -> bool:
        return (
            self.realized_price is not None
            and self.realized_at is not None
            and self.realized_at >= self.horizon_end
        )


def _direction(value: float, reference: float, tolerance: float = 1e-9) -> int:
    delta = value - reference
    if abs(delta) <= tolerance:
        return 0
    return 1 if delta > 0 else -1


def _mae(rows: list[BenchmarkObservation], field: str) -> float | None:
    if not rows:
        return None
    return mean(abs(getattr(row, field) - float(row.realized_price)) for row in rows)


def _mape(rows: list[BenchmarkObservation], field: str) -> float | None:
    eligible = [row for row in rows if row.realized_price not in (None, 0)]
    if not eligible:
        return None
    return mean(
        abs(getattr(row, field) - float(row.realized_price)) / abs(float(row.realized_price))
        for row in eligible
    )


def _directional_accuracy(rows: list[BenchmarkObservation], field: str) -> float | None:
    if not rows:
        return None
    hits = 0
    for row in rows:
        predicted = _direction(getattr(row, field), row.current_price)
        realized = _direction(float(row.realized_price), row.current_price)
        hits += predicted == realized
    return hits / len(rows)


def evaluate_intelligence_vs_baseline(
    observations: Iterable[BenchmarkObservation],
    *,
    min_mature_samples: int = 20,
) -> dict:
    """Compare hierarchy/intelligence estimates with a simple sold-comp baseline.

    Only observations whose full forward horizon has elapsed are scored. This is
    intentionally fail-closed: immature rows stay visible in counts but cannot
    influence error, directional accuracy, or the production-readiness decision.
    """

    rows = list(observations)
    mature = [row for row in rows if row.is_mature]
    immature = [row for row in rows if not row.is_mature]

    baseline_mae = _mae(mature, "baseline_estimate")
    intelligence_mae = _mae(mature, "intelligence_estimate")
    baseline_mape = _mape(mature, "baseline_estimate")
    intelligence_mape = _mape(mature, "intelligence_estimate")
    baseline_direction = _directional_accuracy(mature, "baseline_estimate")
    intelligence_direction = _directional_accuracy(mature, "intelligence_estimate")

    mae_improvement = None
    if baseline_mae not in (None, 0) and intelligence_mae is not None:
        mae_improvement = (baseline_mae - intelligence_mae) / baseline_mae

    mape_improvement = None
    if baseline_mape not in (None, 0) and intelligence_mape is not None:
        mape_improvement = (baseline_mape - intelligence_mape) / baseline_mape

    direction_lift = None
    if baseline_direction is not None and intelligence_direction is not None:
        direction_lift = intelligence_direction - baseline_direction

    production_ready = len(mature) >= min_mature_samples
    blockers: list[str] = []
    if not production_ready:
        blockers.append("insufficient_mature_forward_samples")

    return {
        "total_observations": len(rows),
        "mature_observations": len(mature),
        "immature_observations": len(immature),
        "min_mature_samples": min_mature_samples,
        "baseline": {
            "mae": baseline_mae,
            "mape": baseline_mape,
            "directional_accuracy": baseline_direction,
        },
        "intelligence": {
            "mae": intelligence_mae,
            "mape": intelligence_mape,
            "directional_accuracy": intelligence_direction,
        },
        "lift": {
            "mae_improvement_pct": mae_improvement,
            "mape_improvement_pct": mape_improvement,
            "directional_accuracy_lift": direction_lift,
        },
        "production_ready": production_ready,
        "blockers": blockers,
    }
