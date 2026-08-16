"""Run-level integrity checks for persisted market history and reconstruction lineage."""

from __future__ import annotations

import json
import sqlite3
from typing import Iterable


def _normalized_card_ids(card_ids: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(str(card_id or "").strip() for card_id in card_ids)
    if any(not card_id for card_id in normalized):
        raise ValueError("expected card ids cannot be blank")
    if len(set(normalized)) != len(normalized):
        raise ValueError("expected card ids must be unique")
    return normalized


def audit_market_run_reconstruction(
    conn: sqlite3.Connection,
    run_id: str,
    expected_card_ids: Iterable[str],
) -> dict:
    """Audit whether one market run has complete, internally consistent history.

    The caller supplies the monitored card ids that the run was expected to
    persist. The audit fails closed when snapshots or reconstruction records are
    missing, unexpected, timestamp-inconsistent, orphaned, or when the durable
    reconstruction JSON disagrees with its indexed lineage columns.
    """
    run_id = str(run_id or "").strip()
    if not run_id:
        raise ValueError("run_id is required")
    expected = _normalized_card_ids(expected_card_ids)
    expected_set = set(expected)

    run = conn.execute(
        "SELECT run_id,as_of,status FROM market_runs WHERE run_id=?",
        (run_id,),
    ).fetchone()
    if run is None:
        raise ValueError("market run does not exist")
    run_as_of = str(run["as_of"])

    snapshots = conn.execute(
        "SELECT card_id,as_of,state_json FROM card_market_history WHERE run_id=?",
        (run_id,),
    ).fetchall()
    reconstructions = conn.execute(
        """SELECT record_id,card_id,run_id,as_of,previous_run_id,previous_as_of,record_json
           FROM market_reconstruction_history WHERE run_id=?""",
        (run_id,),
    ).fetchall()

    snapshot_by_card = {str(row["card_id"]): row for row in snapshots}
    reconstruction_by_card = {str(row["card_id"]): row for row in reconstructions}
    snapshot_ids = set(snapshot_by_card)
    reconstruction_ids = set(reconstruction_by_card)

    missing_snapshots = sorted(expected_set - snapshot_ids)
    unexpected_snapshots = sorted(snapshot_ids - expected_set)
    missing_reconstructions = sorted(snapshot_ids - reconstruction_ids)
    orphan_reconstructions = sorted(reconstruction_ids - snapshot_ids)

    snapshot_timestamp_mismatches = sorted(
        card_id
        for card_id, row in snapshot_by_card.items()
        if str(row["as_of"]) != run_as_of
    )
    reconstruction_timestamp_mismatches = sorted(
        card_id
        for card_id, row in reconstruction_by_card.items()
        if str(row["as_of"]) != run_as_of
    )

    malformed_reconstructions = []
    for card_id, row in reconstruction_by_card.items():
        try:
            payload = json.loads(row["record_json"])
        except (TypeError, json.JSONDecodeError):
            malformed_reconstructions.append(card_id)
            continue
        indexed = {
            "record_id": row["record_id"],
            "card_id": row["card_id"],
            "run_id": row["run_id"],
            "as_of": row["as_of"],
            "previous_run_id": row["previous_run_id"],
            "previous_as_of": row["previous_as_of"],
        }
        if payload.get("schema") != "market-reconstruction.v1" or any(
            payload.get(key) != value for key, value in indexed.items()
        ):
            malformed_reconstructions.append(card_id)

    issues = {
        "missing_snapshots": missing_snapshots,
        "unexpected_snapshots": unexpected_snapshots,
        "missing_reconstructions": missing_reconstructions,
        "orphan_reconstructions": orphan_reconstructions,
        "snapshot_timestamp_mismatches": snapshot_timestamp_mismatches,
        "reconstruction_timestamp_mismatches": reconstruction_timestamp_mismatches,
        "malformed_reconstructions": sorted(malformed_reconstructions),
    }
    healthy = not any(issues.values())
    return {
        "schema": "market-run-integrity.v1",
        "run_id": run_id,
        "as_of": run_as_of,
        "run_status": str(run["status"]),
        "status": "healthy" if healthy else "failed",
        "expected_cards": len(expected),
        "persisted_snapshots": len(snapshot_ids),
        "persisted_reconstructions": len(reconstruction_ids),
        "issues": issues,
    }
