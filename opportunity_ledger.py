"""Durable append-only ledger for Opportunity Engine calls.

The product promise is that an opportunity can be judged later exactly as it was
known at the time. This store persists the original sourced Radar decision and
thesis snapshot without allowing silent rewrites.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from opportunity_engine import LedgerEntry, Thesis
from opportunity_radar import RadarCandidate


SCHEMA = "opportunity-ledger.v1"


def _json_default(value: Any) -> Any:
    raw = getattr(value, "value", None)
    if raw is not None:
        return raw
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"unsupported ledger value: {type(value)!r}")


def _dump(value: Any) -> str:
    return json.dumps(value, default=_json_default, sort_keys=True, separators=(",", ":"))


class OpportunityLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS opportunity_calls (
                    thesis_id TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL,
                    player_id TEXT NOT NULL,
                    player TEXT NOT NULL,
                    sport TEXT NOT NULL,
                    thesis_type TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    action TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    market_price_verified INTEGER NOT NULL,
                    blocking_reason TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    source_urls_json TEXT NOT NULL,
                    thesis_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS opportunity_events (
                    thesis_id TEXT NOT NULL,
                    event_index INTEGER NOT NULL,
                    observed_at TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    action TEXT NOT NULL,
                    edge_conviction REAL NOT NULL,
                    evidence_confidence REAL NOT NULL,
                    reason TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    PRIMARY KEY (thesis_id, event_index),
                    FOREIGN KEY (thesis_id) REFERENCES opportunity_calls(thesis_id)
                );
                """
            )

    def persist_candidate(self, candidate: RadarCandidate, events: Iterable[LedgerEntry]) -> None:
        thesis = candidate.thesis
        event_rows = tuple(events)
        if not event_rows:
            raise ValueError("opportunity persistence requires at least one ledger event")
        if any(event.thesis_id != thesis.thesis_id for event in event_rows):
            raise ValueError("ledger event thesis identity mismatch")

        thesis_payload = asdict(thesis)
        source_urls = tuple(candidate.source_urls)
        if not source_urls:
            raise ValueError("opportunity persistence requires source provenance")

        with self._connect() as db:
            existing = db.execute(
                "SELECT thesis_json, decision, source_urls_json FROM opportunity_calls WHERE thesis_id = ?",
                (thesis.thesis_id,),
            ).fetchone()
            if existing is not None:
                same = (
                    existing["thesis_json"] == _dump(thesis_payload)
                    and existing["decision"] == candidate.decision
                    and existing["source_urls_json"] == _dump(source_urls)
                )
                if same:
                    return
                raise ValueError("opportunity call is immutable and cannot be rewritten")

            db.execute(
                """
                INSERT INTO opportunity_calls (
                    thesis_id, schema_version, player_id, player, sport, thesis_type,
                    stage, action, decision, market_price_verified, blocking_reason,
                    created_at, updated_at, source_urls_json, thesis_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    thesis.thesis_id,
                    SCHEMA,
                    thesis.player_id,
                    thesis.player,
                    thesis.sport,
                    thesis.thesis_type.value,
                    thesis.stage.value,
                    thesis.action.value,
                    candidate.decision,
                    int(candidate.market_price_verified),
                    candidate.blocking_reason,
                    thesis.created_at,
                    thesis.updated_at,
                    _dump(source_urls),
                    _dump(thesis_payload),
                ),
            )
            for index, event in enumerate(event_rows):
                payload = asdict(event)
                db.execute(
                    """
                    INSERT INTO opportunity_events (
                        thesis_id, event_index, observed_at, stage, action,
                        edge_conviction, evidence_confidence, reason, event_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        thesis.thesis_id,
                        index,
                        event.observed_at,
                        event.stage.value,
                        event.action.value,
                        event.edge_conviction,
                        event.evidence_confidence,
                        event.reason,
                        _dump(payload),
                    ),
                )

    def get_call(self, thesis_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM opportunity_calls WHERE thesis_id = ?", (thesis_id,)).fetchone()
            if row is None:
                return None
            events = db.execute(
                "SELECT event_json FROM opportunity_events WHERE thesis_id = ? ORDER BY event_index",
                (thesis_id,),
            ).fetchall()
        result = dict(row)
        result["source_urls"] = json.loads(result.pop("source_urls_json"))
        result["thesis"] = json.loads(result.pop("thesis_json"))
        result["events"] = [json.loads(event["event_json"]) for event in events]
        return result

    def list_calls(self) -> tuple[dict[str, Any], ...]:
        with self._connect() as db:
            ids = [row[0] for row in db.execute("SELECT thesis_id FROM opportunity_calls ORDER BY created_at, thesis_id")]
        return tuple(self.get_call(thesis_id) for thesis_id in ids if self.get_call(thesis_id) is not None)
