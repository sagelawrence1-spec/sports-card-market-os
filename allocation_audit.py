"""Persistent audit trail for capital-allocation decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Mapping


@dataclass(frozen=True)
class AllocationDecision:
    run_id: str
    card_id: str
    decided_at: str
    requested_allocation: float
    approved_allocation: float
    ready: bool
    blockers: tuple[str, ...]
    exposure_blockers: tuple[str, ...]
    evidence_grade: str | None
    confidence: float | None
    action: str | None
    details: Mapping[str, Any]


class AllocationAuditStore:
    def __init__(self, database_path: str):
        self.database_path = str(database_path)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS allocation_decisions (
                    run_id TEXT NOT NULL,
                    card_id TEXT NOT NULL,
                    decided_at TEXT NOT NULL,
                    requested_allocation REAL NOT NULL,
                    approved_allocation REAL NOT NULL,
                    ready INTEGER NOT NULL,
                    blockers_json TEXT NOT NULL,
                    exposure_blockers_json TEXT NOT NULL,
                    evidence_grade TEXT,
                    confidence REAL,
                    action TEXT,
                    details_json TEXT NOT NULL,
                    PRIMARY KEY(run_id, card_id)
                )
                """
            )

    def _connect(self):
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def record(self, decision: AllocationDecision) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO allocation_decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(run_id,card_id) DO UPDATE SET
                    decided_at=excluded.decided_at,
                    requested_allocation=excluded.requested_allocation,
                    approved_allocation=excluded.approved_allocation,
                    ready=excluded.ready,
                    blockers_json=excluded.blockers_json,
                    exposure_blockers_json=excluded.exposure_blockers_json,
                    evidence_grade=excluded.evidence_grade,
                    confidence=excluded.confidence,
                    action=excluded.action,
                    details_json=excluded.details_json
                """,
                (
                    decision.run_id,
                    decision.card_id,
                    decision.decided_at,
                    decision.requested_allocation,
                    decision.approved_allocation,
                    int(decision.ready),
                    json.dumps(list(decision.blockers), sort_keys=True),
                    json.dumps(list(decision.exposure_blockers), sort_keys=True),
                    decision.evidence_grade,
                    decision.confidence,
                    decision.action,
                    json.dumps(dict(decision.details), sort_keys=True),
                ),
            )

    def load_run(self, run_id: str) -> list[AllocationDecision]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM allocation_decisions WHERE run_id=? ORDER BY card_id",
                (run_id,),
            ).fetchall()
        return [
            AllocationDecision(
                run_id=row["run_id"],
                card_id=row["card_id"],
                decided_at=row["decided_at"],
                requested_allocation=row["requested_allocation"],
                approved_allocation=row["approved_allocation"],
                ready=bool(row["ready"]),
                blockers=tuple(json.loads(row["blockers_json"])),
                exposure_blockers=tuple(json.loads(row["exposure_blockers_json"])),
                evidence_grade=row["evidence_grade"],
                confidence=row["confidence"],
                action=row["action"],
                details=json.loads(row["details_json"]),
            )
            for row in rows
        ]


def persist_allocation_run(
    store: AllocationAuditStore,
    *,
    run_id: str,
    allocations: list[Mapping[str, Any]],
    decided_at: str | None = None,
) -> int:
    """Persist final allocation decisions without changing upstream amounts."""
    timestamp = decided_at or datetime.now(timezone.utc).isoformat()
    count = 0
    for row in allocations:
        card_id = str(row.get("card_id") or "")
        if not card_id:
            continue

        requested = float(row.get("allocation") or 0.0)
        approved_raw = row.get("exposure_adjusted_allocation")
        approved = float(requested if approved_raw is None else approved_raw)

        if requested < 0 or approved < 0:
            raise ValueError("Allocation amounts cannot be negative.")
        if approved > requested + 1e-9:
            raise ValueError("Audit layer cannot increase an upstream allocation.")

        store.record(
            AllocationDecision(
                run_id=run_id,
                card_id=card_id,
                decided_at=timestamp,
                requested_allocation=requested,
                approved_allocation=approved,
                ready=bool(row.get("ready")),
                blockers=tuple(row.get("blockers") or ()),
                exposure_blockers=tuple(row.get("exposure_blockers") or ()),
                evidence_grade=row.get("evidence_grade"),
                confidence=float(row["confidence"]) if row.get("confidence") is not None else None,
                action=row.get("action"),
                details={
                    "track_record": row.get("track_record"),
                    "exposure_headroom": row.get("exposure_headroom"),
                    "upside": row.get("upside"),
                },
            )
        )
        count += 1
    return count
