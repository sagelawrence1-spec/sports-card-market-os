from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
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

    def is_mature_at(self, evaluation_date: date) -> bool:
        return (
            self.realized_price is not None
            and self.realized_at is not None
            and self.realized_at >= self.horizon_end
            and self.realized_at <= evaluation_date
            and self.horizon_end <= evaluation_date
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
    evaluation_date: date | None = None,
    min_mature_samples: int = 20,
) -> dict:
    """Compare intelligence estimates with a simple sold-comp baseline.

    The evaluation date is explicit so a benchmark replay cannot accidentally score
    outcomes that were not known at that point in time. Mature rows must have a full
    elapsed horizon and a realized observation at or before the evaluation date.
    """

    evaluation_date = evaluation_date or date.today()
    rows = list(observations)
    mature = [row for row in rows if row.is_mature_at(evaluation_date)]
    immature = [row for row in rows if not row.is_mature_at(evaluation_date)]

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

    blockers: list[str] = []
    if len(mature) < min_mature_samples:
        blockers.append("insufficient_mature_forward_samples")

    return {
        "evaluation_date": evaluation_date.isoformat(),
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
        "production_ready": not blockers,
        "blockers": blockers,
    }


class IntelligenceBenchmarkStore:
    """SQLite-backed point-in-time benchmark journal.

    Observation identity is card + as-of date + horizon. Re-running a scan updates
    that point deterministically rather than duplicating it. Benchmark run summaries
    are append-only so calibration decisions remain auditable across restarts.
    """

    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS intelligence_benchmark_observations (
                    card_id TEXT NOT NULL,
                    as_of_date TEXT NOT NULL,
                    horizon_days INTEGER NOT NULL,
                    current_price REAL NOT NULL,
                    baseline_estimate REAL NOT NULL,
                    intelligence_estimate REAL NOT NULL,
                    realized_price REAL,
                    realized_at TEXT,
                    evidence_grade TEXT,
                    confidence REAL,
                    PRIMARY KEY (card_id, as_of_date, horizon_days)
                );

                CREATE TABLE IF NOT EXISTS intelligence_benchmark_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    evaluated_at TEXT NOT NULL,
                    min_mature_samples INTEGER NOT NULL,
                    result_json TEXT NOT NULL
                );
                """
            )

    def upsert_observation(self, observation: BenchmarkObservation) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO intelligence_benchmark_observations (
                    card_id, as_of_date, horizon_days, current_price,
                    baseline_estimate, intelligence_estimate, realized_price,
                    realized_at, evidence_grade, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(card_id, as_of_date, horizon_days) DO UPDATE SET
                    current_price = excluded.current_price,
                    baseline_estimate = excluded.baseline_estimate,
                    intelligence_estimate = excluded.intelligence_estimate,
                    realized_price = excluded.realized_price,
                    realized_at = excluded.realized_at,
                    evidence_grade = excluded.evidence_grade,
                    confidence = excluded.confidence
                """,
                (
                    observation.card_id,
                    observation.as_of_date.isoformat(),
                    observation.horizon_days,
                    observation.current_price,
                    observation.baseline_estimate,
                    observation.intelligence_estimate,
                    observation.realized_price,
                    observation.realized_at.isoformat() if observation.realized_at else None,
                    observation.evidence_grade,
                    observation.confidence,
                ),
            )

    def load_observations(self) -> list[BenchmarkObservation]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM intelligence_benchmark_observations
                ORDER BY as_of_date, card_id, horizon_days
                """
            ).fetchall()
        return [
            BenchmarkObservation(
                card_id=row["card_id"],
                as_of_date=date.fromisoformat(row["as_of_date"]),
                horizon_days=row["horizon_days"],
                current_price=row["current_price"],
                baseline_estimate=row["baseline_estimate"],
                intelligence_estimate=row["intelligence_estimate"],
                realized_price=row["realized_price"],
                realized_at=date.fromisoformat(row["realized_at"]) if row["realized_at"] else None,
                evidence_grade=row["evidence_grade"],
                confidence=row["confidence"],
            )
            for row in rows
        ]

    def evaluate_and_record(
        self,
        *,
        evaluation_date: date | None = None,
        min_mature_samples: int = 20,
    ) -> dict:
        evaluation_date = evaluation_date or date.today()
        result = evaluate_intelligence_vs_baseline(
            self.load_observations(),
            evaluation_date=evaluation_date,
            min_mature_samples=min_mature_samples,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO intelligence_benchmark_runs (
                    evaluated_at, min_mature_samples, result_json
                ) VALUES (?, ?, ?)
                """,
                (evaluation_date.isoformat(), min_mature_samples, json.dumps(result, sort_keys=True)),
            )
        return result

    def load_runs(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT evaluated_at, min_mature_samples, result_json
                FROM intelligence_benchmark_runs ORDER BY id
                """
            ).fetchall()
        return [
            {
                "evaluated_at": row["evaluated_at"],
                "min_mature_samples": row["min_mature_samples"],
                "result": json.loads(row["result_json"]),
            }
            for row in rows
        ]
