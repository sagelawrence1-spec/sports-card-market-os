"""Append-only persistence for final Opportunity Engine decision packets.

The Radar ledger preserves the original thesis. This store preserves the exact
reviewable decision packet after authoritative repricing has been applied so
later outcome grading can prove what action and evidence existed at decision
time without hindsight rewrites.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA = "opportunity-decision-ledger.v1"
PACKET_SCHEMA = "opportunity-decision-packet.v1"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _packet_identity(packet: Mapping[str, Any]) -> tuple[str, str, str, str]:
    if packet.get("schema") != PACKET_SCHEMA:
        raise ValueError("unsupported opportunity decision packet schema")
    player_id = str(packet.get("player_id", "")).strip()
    card = packet.get("card")
    card_id = str(card.get("card_id", "")).strip() if isinstance(card, Mapping) else ""
    catalyst_at = str(packet.get("catalyst_at", "")).strip()
    as_of = str(packet.get("as_of", "")).strip()
    if not player_id or not card_id or not catalyst_at or not as_of:
        raise ValueError("decision packet requires player_id, card.card_id, catalyst_at, and as_of")
    return player_id, card_id, catalyst_at, as_of


def decision_packet_id(packet: Mapping[str, Any]) -> str:
    """Return a stable content digest for the exact packet presented for review."""
    _packet_identity(packet)
    return hashlib.sha256(_canonical_json(dict(packet)).encode("utf-8")).hexdigest()


def _validated_record(packet: Mapping[str, Any]) -> tuple[str, tuple[str, str, str, str], str, str, bool]:
    player_id, card_id, catalyst_at, as_of = _packet_identity(packet)
    decision = str(packet.get("decision", "")).strip()
    actionable = packet.get("actionable")
    if not decision or not isinstance(actionable, bool):
        raise ValueError("decision packet requires decision and boolean actionable")
    payload = _canonical_json(dict(packet))
    packet_id = decision_packet_id(packet)
    return packet_id, (player_id, card_id, catalyst_at, as_of), payload, decision, actionable


class OpportunityDecisionLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS opportunity_decisions (
                    decision_id TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL,
                    player_id TEXT NOT NULL,
                    card_id TEXT NOT NULL,
                    catalyst_at TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    actionable INTEGER NOT NULL,
                    packet_json TEXT NOT NULL,
                    UNIQUE(player_id, card_id, catalyst_at, as_of)
                )
                """
            )

    def persist_packet(self, packet: Mapping[str, Any]) -> str:
        return self.persist_packets_atomic((packet,))[0]

    def persist_packets_atomic(self, packets: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
        """Persist a decision batch in one transaction or write nothing.

        Exact retries are idempotent. If any packet conflicts with immutable history
        or the batch itself contains two different packets for the same natural key,
        the entire batch fails and no new packet is committed.
        """
        if isinstance(packets, (str, bytes)) or not isinstance(packets, Sequence):
            raise ValueError("packets must be a sequence")
        if not packets:
            return ()

        records = []
        seen: dict[tuple[str, str, str, str], tuple[str, str]] = {}
        for packet in packets:
            if not isinstance(packet, Mapping):
                raise ValueError("each decision packet must be an object")
            record = _validated_record(packet)
            packet_id, natural_key, payload, decision, actionable = record
            prior = seen.get(natural_key)
            if prior is not None and prior != (packet_id, payload):
                raise ValueError("decision batch contains conflicting immutable decision packets")
            seen[natural_key] = (packet_id, payload)
            records.append((packet_id, natural_key, payload, decision, actionable))

        with self._connect() as db:
            for packet_id, natural_key, payload, _, _ in records:
                existing = db.execute(
                    """
                    SELECT decision_id, packet_json
                    FROM opportunity_decisions
                    WHERE player_id = ? AND card_id = ? AND catalyst_at = ? AND as_of = ?
                    """,
                    natural_key,
                ).fetchone()
                if existing is not None and not (
                    existing["decision_id"] == packet_id and existing["packet_json"] == payload
                ):
                    raise ValueError("opportunity decision is immutable and cannot be rewritten")

            for packet_id, natural_key, payload, decision, actionable in records:
                player_id, card_id, catalyst_at, as_of = natural_key
                db.execute(
                    """
                    INSERT OR IGNORE INTO opportunity_decisions (
                        decision_id, schema_version, player_id, card_id, catalyst_at,
                        as_of, decision, actionable, packet_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        packet_id,
                        SCHEMA,
                        player_id,
                        card_id,
                        catalyst_at,
                        as_of,
                        decision,
                        int(actionable),
                        payload,
                    ),
                )
        return tuple(record[0] for record in records)

    def get_packet(self, packet_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT packet_json FROM opportunity_decisions WHERE decision_id = ?",
                (packet_id,),
            ).fetchone()
        return None if row is None else json.loads(row["packet_json"])

    def list_packets(self) -> tuple[dict[str, Any], ...]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT packet_json FROM opportunity_decisions ORDER BY as_of, decision_id"
            ).fetchall()
        return tuple(json.loads(row["packet_json"]) for row in rows)
