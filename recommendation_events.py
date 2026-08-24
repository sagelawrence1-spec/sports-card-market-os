"""Append-only lifecycle events for published recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import sqlite3


LIFECYCLE_EVENT_TYPES = frozenset({"CLOSED", "INVALIDATED"})


@dataclass(frozen=True)
class RecommendationEvent:
    event_id: str
    observation_id: str
    as_of_date: date
    horizon_days: int
    event_type: str
    occurred_at: date
    reason: str


class RecommendationEventStore:
    """Persist closes/invalidations without rewriting the original recommendation."""

    def __init__(self, database_path: str):
        self.database_path = str(database_path)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS recommendation_events (
                    event_id TEXT PRIMARY KEY,
                    observation_id TEXT NOT NULL,
                    as_of_date TEXT NOT NULL,
                    horizon_days INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    reason TEXT NOT NULL
                )
                """
            )

    def _connect(self):
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _fields(event: RecommendationEvent) -> tuple[object, ...]:
        return (
            event.observation_id,
            event.as_of_date.isoformat(),
            event.horizon_days,
            event.event_type,
            event.occurred_at.isoformat(),
            event.reason,
        )

    @staticmethod
    def _row_fields(row: sqlite3.Row) -> tuple[object, ...]:
        return (
            row["observation_id"],
            row["as_of_date"],
            row["horizon_days"],
            row["event_type"],
            row["occurred_at"],
            row["reason"],
        )

    def append(self, event: RecommendationEvent) -> None:
        if not isinstance(event.event_id, str) or not event.event_id.strip():
            raise ValueError("Lifecycle event_id must be non-blank text.")
        if event.event_type not in LIFECYCLE_EVENT_TYPES:
            raise ValueError("Lifecycle event_type must be CLOSED or INVALIDATED.")
        if isinstance(event.horizon_days, bool) or not isinstance(event.horizon_days, int) or event.horizon_days <= 0:
            raise ValueError("Lifecycle horizon_days must be a positive integer.")
        if event.occurred_at < event.as_of_date:
            raise ValueError("Lifecycle events cannot predate the recommendation.")
        if not isinstance(event.reason, str) or not event.reason.strip():
            raise ValueError("Lifecycle event reason must be non-blank text.")

        key = (event.observation_id, event.as_of_date.isoformat(), event.horizon_days)
        with self._connect() as conn:
            recommendation = conn.execute(
                """
                SELECT 1 FROM recommendation_journal
                WHERE observation_id=? AND as_of_date=? AND horizon_days=?
                """,
                key,
            ).fetchone()
            if recommendation is None:
                raise ValueError("Lifecycle event must reference an existing recommendation.")

            existing = conn.execute(
                "SELECT * FROM recommendation_events WHERE event_id=?",
                (event.event_id,),
            ).fetchone()
            if existing is not None:
                if self._row_fields(existing) != self._fields(event):
                    raise ValueError("Published lifecycle events are immutable.")
                return

            conn.execute(
                """
                INSERT INTO recommendation_events
                (event_id, observation_id, as_of_date, horizon_days, event_type, occurred_at, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (event.event_id, *self._fields(event)),
            )

    def load(self, observation_id: str | None = None) -> list[RecommendationEvent]:
        query = "SELECT * FROM recommendation_events"
        params: tuple[object, ...] = ()
        if observation_id is not None:
            query += " WHERE observation_id=?"
            params = (observation_id,)
        query += " ORDER BY occurred_at, event_id"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            RecommendationEvent(
                event_id=row["event_id"],
                observation_id=row["observation_id"],
                as_of_date=date.fromisoformat(row["as_of_date"]),
                horizon_days=row["horizon_days"],
                event_type=row["event_type"],
                occurred_at=date.fromisoformat(row["occurred_at"]),
                reason=row["reason"],
            )
            for row in rows
        ]
