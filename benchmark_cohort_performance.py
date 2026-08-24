from __future__ import annotations

from datetime import date
from statistics import mean
from typing import Iterable

from intelligence_benchmark import BenchmarkObservation


def _direction(value: float, reference: float, tolerance: float = 1e-9) -> int:
    delta = float(value) - float(reference)
    if abs(delta) <= tolerance:
        return 0
    return 1 if delta > 0 else -1


def _target_price(row: BenchmarkObservation) -> float:
    value = row.net_realized_price
    if value is None:
        raise ValueError("cohort performance requires mature realized outcomes")
    return float(value)


def _confidence_band(confidence: float | None) -> str:
    if confidence is None:
        return "unknown"
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.6:
        return "medium"
    return "low"


def _forecast_hit(row: BenchmarkObservation, field: str) -> bool:
    return _direction(getattr(row, field), row.current_price) == _direction(
        _target_price(row), row.current_price
    )


def _valuation_error_pct(rows: list[BenchmarkObservation], field: str) -> float | None:
    if not rows:
        return None
    return mean(
        abs(float(getattr(row, field)) - _target_price(row)) / _target_price(row)
        for row in rows
    )


def _hit_rate(rows: list[BenchmarkObservation], field: str) -> float | None:
    if not rows:
        return None
    return mean(1.0 if _forecast_hit(row, field) else 0.0 for row in rows)


def _max_drawdown_pct(rows: list[BenchmarkObservation], field: str) -> float | None:
    """Maximum additive drawdown of unit-notional directional forecast returns.

    Each mature decision contributes a signed realized return from its decision-time
    current price. Rows are replayed chronologically and cumulative P&L is measured
    from the prior high-water mark. Additive unit-notional accounting is deliberate:
    benchmark observations overlap in time and do not imply a compounding portfolio.
    """

    if not rows:
        return None
    cumulative_return = 0.0
    peak_return = 0.0
    max_drawdown = 0.0
    ordered = sorted(rows, key=lambda row: (row.as_of_date, row.card_id, row.horizon_days))
    for row in ordered:
        forecast_direction = _direction(getattr(row, field), row.current_price)
        realized_return = (_target_price(row) - float(row.current_price)) / float(row.current_price)
        cumulative_return += forecast_direction * realized_return
        peak_return = max(peak_return, cumulative_return)
        max_drawdown = max(max_drawdown, peak_return - cumulative_return)
    return max_drawdown


def _calibration_error(rows: list[BenchmarkObservation]) -> float | None:
    eligible = [row for row in rows if row.confidence is not None]
    if not eligible:
        return None
    return mean(
        abs(float(row.confidence) - (1.0 if _forecast_hit(row, "intelligence_estimate") else 0.0))
        for row in eligible
    )


def _performance_block(rows: list[BenchmarkObservation]) -> dict:
    return {
        "observations": len(rows),
        "baseline": {
            "hit_rate": _hit_rate(rows, "baseline_estimate"),
            "valuation_error_mae_pct": _valuation_error_pct(rows, "baseline_estimate"),
            "max_drawdown_pct": _max_drawdown_pct(rows, "baseline_estimate"),
        },
        "intelligence": {
            "hit_rate": _hit_rate(rows, "intelligence_estimate"),
            "valuation_error_mae_pct": _valuation_error_pct(rows, "intelligence_estimate"),
            "max_drawdown_pct": _max_drawdown_pct(rows, "intelligence_estimate"),
            "calibration_error_mae": _calibration_error(rows),
        },
    }


def _segment(
    rows: list[BenchmarkObservation], key_fn
) -> dict[str, dict]:
    grouped: dict[str, list[BenchmarkObservation]] = {}
    for row in rows:
        grouped.setdefault(key_fn(row), []).append(row)
    return {key: _performance_block(grouped[key]) for key in sorted(grouped)}


def benchmark_cohort_performance(
    observations: Iterable[BenchmarkObservation], *, evaluation_date: date
) -> dict:
    """Report leakage-safe performance accounting overall and by benchmark cohort."""

    rows = list(observations)
    mature = [row for row in rows if row.is_mature_at(evaluation_date)]
    return {
        "basis": {
            "outcome": "net_realized_after_exit_fees_and_liquidity_haircut",
            "drawdown": "chronological_additive_unit_notional_directional_returns",
            "calibration": "mean_absolute_confidence_error_vs_directional_hit",
        },
        "overall": _performance_block(mature),
        "cohorts": {
            "evidence_grade": _segment(
                mature, lambda row: row.evidence_grade or "unknown"
            ),
            "confidence_band": _segment(
                mature, lambda row: _confidence_band(row.confidence)
            ),
        },
    }
