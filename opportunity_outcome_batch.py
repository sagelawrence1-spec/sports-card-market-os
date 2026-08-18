"""Batch authoritative forward outcome grading for Opportunity Engine decisions."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from opportunity_outcome_collection import grade_authoritative_market_outcome
from opportunity_outcomes import OpportunityOutcomePolicy

OUTPUT_SCHEMA = "opportunity-authoritative-outcome-batch.v1"


def grade_authoritative_outcome_batch(
    jobs: Iterable[Mapping[str, Any]],
    *,
    as_of: str,
    min_forward_comps: int = 3,
    policy: OpportunityOutcomePolicy | None = None,
) -> dict[str, Any]:
    """Grade a set of settled decisions without hand-selecting favorable outcomes.

    Each job must bind one immutable decision packet to its original entry collection,
    canonical asset, and forward Product Research CSV. Job failures stay explicit and
    do not disappear from the batch proof artifact.
    """
    rows = list(jobs)
    if not rows:
        raise ValueError("jobs must not be empty")

    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    graded = blocked = failed = 0

    for index, job in enumerate(rows):
        packet = job.get("packet")
        entry_collection = job.get("entry_collection")
        asset = job.get("asset")
        csv_path = job.get("csv_path")
        if not isinstance(packet, Mapping) or not isinstance(entry_collection, Mapping) or not isinstance(asset, Mapping) or not csv_path:
            failed += 1
            results.append({"index": index, "status": "FAILED", "reason": "incomplete_job"})
            continue

        card = packet.get("card")
        card_id = str(card.get("card_id", "")).strip() if isinstance(card, Mapping) else ""
        player_id = str(packet.get("player_id", "")).strip()
        decision_as_of = str(packet.get("as_of", "")).strip()
        identity = (player_id, card_id, decision_as_of)
        if not all(identity):
            failed += 1
            results.append({"index": index, "status": "FAILED", "reason": "incomplete_decision_identity"})
            continue
        if identity in seen:
            failed += 1
            results.append({"index": index, "player_id": player_id, "card_id": card_id, "status": "FAILED", "reason": "duplicate_decision"})
            continue
        seen.add(identity)

        try:
            proof = grade_authoritative_market_outcome(
                packet,
                entry_collection,
                asset=asset,
                csv_path=Path(str(csv_path)),
                as_of=as_of,
                min_forward_comps=min_forward_comps,
                policy=policy,
            )
        except (ValueError, TypeError, FileNotFoundError) as exc:
            failed += 1
            results.append({
                "index": index,
                "player_id": player_id,
                "card_id": card_id,
                "status": "FAILED",
                "reason": str(exc),
            })
            continue

        if proof.get("graded"):
            graded += 1
            status = "GRADED"
        else:
            blocked += 1
            status = "BLOCKED"
        results.append({
            "index": index,
            "player_id": player_id,
            "card_id": card_id,
            "status": status,
            "proof": proof,
        })

    return {
        "schema": OUTPUT_SCHEMA,
        "as_of": as_of,
        "input_count": len(rows),
        "graded_count": graded,
        "blocked_count": blocked,
        "failed_count": failed,
        "complete": failed == 0 and blocked == 0 and graded == len(rows),
        "results": results,
    }
