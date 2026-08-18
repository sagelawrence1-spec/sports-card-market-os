"""Execute mature authoritative outcome manifest items as one proof batch."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from opportunity_outcome_batch import grade_authoritative_outcome_batch

OUTPUT_SCHEMA = "opportunity-authoritative-outcome-run.v1"
MANIFEST_SCHEMA = "opportunity-authoritative-outcome-manifest.v1"


def run_authoritative_outcome_manifest(
    manifest: Mapping[str, Any],
    *,
    assets: Mapping[str, Mapping[str, Any]],
    export_dir: str | Path,
    min_forward_comps: int = 3,
) -> dict[str, Any]:
    """Grade every mature manifest item without hand-assembling batch jobs.

    Waiting-horizon and ineligible decisions remain visible in the run artifact but
    are never graded early. Every mature item is forwarded to the authoritative
    batch grader; missing assets or exports therefore remain explicit failures.
    """
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unsupported authoritative outcome manifest schema")
    items = manifest.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("manifest items must be a non-empty array")
    if not isinstance(assets, Mapping):
        raise ValueError("assets must be an object keyed by card_id")

    root = Path(export_dir)
    jobs: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    waiting = ineligible = 0

    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("each manifest item must be an object")
        status = str(item.get("status", "")).strip()
        if status == "WAITING_HORIZON":
            waiting += 1
            continue
        if status == "INELIGIBLE":
            ineligible += 1
            continue
        if status != "MATURE":
            raise ValueError(f"unsupported manifest item status: {status or 'missing'}")

        packet = item.get("packet")
        entry_collection = item.get("entry_collection")
        player_id = str(item.get("player_id", "")).strip()
        card_id = str(item.get("card_id", "")).strip()
        decision_as_of = str(item.get("decision_as_of", "")).strip()
        filename = str(item.get("expected_export_filename", "")).strip()
        identity = (player_id, card_id, decision_as_of)
        if not all(identity) or not filename:
            raise ValueError("mature manifest item identity/export filename is incomplete")
        if identity in seen:
            raise ValueError("duplicate mature manifest decision identity")
        seen.add(identity)

        jobs.append({
            "packet": packet,
            "entry_collection": entry_collection,
            "asset": assets.get(card_id),
            "csv_path": root / filename,
        })

    expected_mature = int(manifest.get("mature_count", len(jobs)))
    if expected_mature != len(jobs):
        raise ValueError("manifest mature_count does not match mature items")

    as_of = str(manifest.get("as_of", "")).strip()
    if not as_of:
        raise ValueError("manifest as_of is required")

    if jobs:
        batch = grade_authoritative_outcome_batch(
            jobs,
            as_of=as_of,
            min_forward_comps=min_forward_comps,
        )
    else:
        batch = {
            "schema": "opportunity-authoritative-outcome-batch.v1",
            "as_of": as_of,
            "input_count": 0,
            "graded_count": 0,
            "blocked_count": 0,
            "failed_count": 0,
            "complete": True,
            "results": [],
        }

    return {
        "schema": OUTPUT_SCHEMA,
        "manifest_as_of": as_of,
        "manifest_input_count": int(manifest.get("input_count", len(items))),
        "mature_count": len(jobs),
        "waiting_horizon_count": waiting,
        "ineligible_count": ineligible,
        "minimum_forward_comps": int(min_forward_comps),
        "complete": batch.get("complete") is True,
        "batch": batch,
    }
