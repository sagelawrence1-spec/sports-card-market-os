"""Build reviewable Opportunity Engine decision packets from a repricing batch."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from opportunity_decision_packet import build_opportunity_decision_packet


def _observation_index(observations: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    if isinstance(observations, Mapping):
        values = list(observations.values())
    elif isinstance(observations, Sequence) and not isinstance(observations, (str, bytes)):
        values = list(observations)
    else:
        raise ValueError("observations must be an object or list")

    index: dict[str, Mapping[str, Any]] = {}
    for observation in values:
        if not isinstance(observation, Mapping):
            raise ValueError("each observation must be an object")
        player_id = str(observation.get("player_id", "")).strip()
        if not player_id:
            raise ValueError("each observation requires player_id")
        if player_id in index:
            raise ValueError(f"duplicate observation player_id: {player_id}")
        index[player_id] = observation
    return index


def build_opportunity_decision_batch(
    collection_batch: Mapping[str, Any],
    *,
    observations: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Convert one authoritative repricing batch into decision-ready packets.

    Only successfully collected repricing artifacts are evaluated. Missing exports,
    assets, and collection failures remain explicit blockers instead of disappearing.
    """
    if collection_batch.get("schema") != "opportunity-repricing-batch.v1":
        raise ValueError("unsupported repricing batch schema")
    raw_results = collection_batch.get("results")
    if not isinstance(raw_results, list):
        raise ValueError("repricing batch results must be a list")

    observation_by_player = _observation_index(observations)
    results: list[dict[str, Any]] = []
    packet_count = 0
    actionable_count = 0
    blocked_count = 0
    failed_count = 0

    for row in raw_results:
        if not isinstance(row, Mapping):
            raise ValueError("repricing batch result must be an object")
        card_id = str(row.get("card_id", "")).strip()
        status = str(row.get("status", "")).strip()
        if not card_id or not status:
            raise ValueError("repricing batch result requires card_id and status")

        if status != "COLLECTED":
            blocked_count += 1
            results.append(
                {
                    "card_id": card_id,
                    "status": status,
                    "decision_status": "BLOCKED",
                    "blocking_reason": status,
                    "csv_path": row.get("csv_path"),
                    "error": row.get("error"),
                }
            )
            continue

        collection = row.get("artifact")
        if not isinstance(collection, Mapping) or collection.get("schema") != "opportunity-repricing-collection.v1":
            failed_count += 1
            results.append(
                {
                    "card_id": card_id,
                    "status": status,
                    "decision_status": "FAILED",
                    "blocking_reason": "INVALID_COLLECTION_ARTIFACT",
                }
            )
            continue

        player_id = str(collection.get("player_id", "")).strip()
        if not player_id:
            raise ValueError("collected repricing artifact requires player_id")
        observation = observation_by_player.get(player_id)
        if observation is None:
            blocked_count += 1
            results.append(
                {
                    "player_id": player_id,
                    "card_id": card_id,
                    "status": status,
                    "decision_status": "BLOCKED",
                    "blocking_reason": "MISSING_OBSERVATION",
                }
            )
            continue

        try:
            packet = build_opportunity_decision_packet(observation, collection)
        except (KeyError, TypeError, ValueError) as exc:
            failed_count += 1
            results.append(
                {
                    "player_id": player_id,
                    "card_id": card_id,
                    "status": status,
                    "decision_status": "FAILED",
                    "blocking_reason": "DECISION_PACKET_FAILED",
                    "error": str(exc),
                }
            )
            continue

        packet_count += 1
        if bool(packet.get("actionable")):
            actionable_count += 1
        results.append(
            {
                "player_id": player_id,
                "card_id": card_id,
                "status": status,
                "decision_status": "READY",
                "decision": packet.get("decision"),
                "actionable": bool(packet.get("actionable")),
                "packet": packet,
            }
        )

    return {
        "schema": "opportunity-decision-batch.v1",
        "source_manifest_generated_at": collection_batch.get("source_manifest_generated_at"),
        "requested_count": len(raw_results),
        "packet_count": packet_count,
        "actionable_count": actionable_count,
        "blocked_count": blocked_count,
        "failed_count": failed_count,
        "ready": packet_count == len(raw_results) and blocked_count == 0 and failed_count == 0,
        "results": results,
    }
