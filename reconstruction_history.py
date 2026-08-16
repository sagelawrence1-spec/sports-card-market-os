"""Durable persistence for lineage-bearing market reconstruction records."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Mapping


RECONSTRUCTION_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS market_reconstruction_history(
  record_id TEXT PRIMARY KEY,
  card_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  as_of TEXT NOT NULL,
  previous_run_id TEXT,
  previous_as_of TEXT,
  record_json TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(run_id, card_id)
);
CREATE INDEX IF NOT EXISTS idx_reconstruction_history_card
  ON market_reconstruction_history(card_id, as_of);
"""


def ensure_reconstruction_history_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(RECONSTRUCTION_HISTORY_SCHEMA)


def _require_snapshot(conn: sqlite3.Connection, run_id: str, card_id: str, as_of: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM card_market_history WHERE run_id=? AND card_id=? AND as_of=?",
        (run_id, card_id, as_of),
    ).fetchone()
    if row is None:
        raise ValueError("reconstruction lineage must reference persisted market snapshots")


def persist_reconstruction_record(
    conn: sqlite3.Connection,
    record: Mapping[str, Any],
) -> str:
    """Persist one immutable reconstruction record after validating its lineage.

    Records are append-only. Both the current and predecessor references must
    already exist in ``card_market_history`` so a delta can never outlive or
    point at an unpersisted snapshot.
    """
    ensure_reconstruction_history_schema(conn)

    if record.get("schema") != "market-reconstruction.v1":
        raise ValueError("unsupported reconstruction record schema")

    record_id = str(record.get("record_id") or "").strip()
    card_id = str(record.get("card_id") or "").strip()
    run_id = str(record.get("run_id") or "").strip()
    as_of = str(record.get("as_of") or "").strip()
    if not all((record_id, card_id, run_id, as_of)):
        raise ValueError("reconstruction record requires record_id, card_id, run_id, and as_of")

    previous_run_id = record.get("previous_run_id")
    previous_as_of = record.get("previous_as_of")
    if (previous_run_id is None) != (previous_as_of is None):
        raise ValueError("predecessor run and timestamp must be present together")

    _require_snapshot(conn, run_id, card_id, as_of)
    if previous_run_id is not None:
        previous_run_id = str(previous_run_id).strip()
        previous_as_of = str(previous_as_of).strip()
        if not previous_run_id or not previous_as_of:
            raise ValueError("predecessor lineage cannot be blank")
        if previous_as_of >= as_of:
            raise ValueError("predecessor reconstruction snapshot must be strictly earlier")
        _require_snapshot(conn, previous_run_id, card_id, previous_as_of)

    payload = json.dumps(dict(record), sort_keys=True)
    try:
        conn.execute(
            """INSERT INTO market_reconstruction_history(
              record_id,card_id,run_id,as_of,previous_run_id,previous_as_of,record_json
              ) VALUES(?,?,?,?,?,?,?)""",
            (record_id, card_id, run_id, as_of, previous_run_id, previous_as_of, payload),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError("reconstruction history is append-only for each run/card pair") from exc
    conn.commit()
    return record_id


def reconstruction_history(conn: sqlite3.Connection, card_id: str) -> list[dict[str, Any]]:
    ensure_reconstruction_history_schema(conn)
    rows = conn.execute(
        "SELECT record_json FROM market_reconstruction_history WHERE card_id=? ORDER BY as_of,rowid",
        (card_id,),
    ).fetchall()
    return [json.loads(row[0]) for row in rows]
