"""Human-executable forward Product Research manifest for settled Opportunity calls."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from opportunity_outcomes import OpportunityOutcomePolicy

OUTPUT_SCHEMA = "opportunity-authoritative-outcome-manifest.v1"
_ACTIONABLE = {"START_POSITION", "ADD"}


def _aware(value: Any, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _safe_filename(value: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-.").lower()
    return token or "unknown"


def build_authoritative_outcome_manifest(
    jobs: Iterable[Mapping[str, Any]],
    *,
    as_of: str,
    policy: OpportunityOutcomePolicy | None = None,
) -> dict[str, Any]:
    """Build the complete forward-comp work queue without cherry-picking decisions."""
    policy = policy or OpportunityOutcomePolicy()
    policy.validate()
    as_of_dt = _aware(as_of, field="as_of")
    rows = list(jobs)
    if not rows:
        raise ValueError("jobs must not be empty")

    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    waiting = mature = ineligible = 0

    for index, job in enumerate(rows):
        if not isinstance(job, Mapping):
            raise ValueError("each job must be an object")
        packet = job.get("packet")
        entry_collection = job.get("entry_collection")
        if not isinstance(packet, Mapping) or not isinstance(entry_collection, Mapping):
            raise ValueError("each job requires packet and entry_collection")
        if packet.get("schema") != "opportunity-decision-packet.v1":
            raise ValueError("unsupported opportunity decision packet schema")

        player_id = str(packet.get("player_id", "")).strip()
        card = packet.get("card")
        card_id = str(card.get("card_id", "")).strip() if isinstance(card, Mapping) else ""
        decision_as_of = str(packet.get("as_of", "")).strip()
        if not player_id or not card_id or not decision_as_of:
            raise ValueError("decision packet identity is incomplete")
        identity = (player_id, card_id, decision_as_of)
        if identity in seen:
            raise ValueError("duplicate decision identity")
        seen.add(identity)

        decision = str(packet.get("decision", "")).strip()
        actionable = packet.get("actionable") is True and decision in _ACTIONABLE
        decision_at = _aware(decision_as_of, field="decision packet as_of")
        horizon_end = decision_at + timedelta(days=int(policy.min_horizon_days))
        status = "MATURE" if actionable and as_of_dt >= horizon_end else "WAITING_HORIZON" if actionable else "INELIGIBLE"
        if status == "MATURE":
            mature += 1
        elif status == "WAITING_HORIZON":
            waiting += 1
        else:
            ineligible += 1

        player = str(packet.get("player") or player_id)
        card_label = str(card.get("label") or card_id) if isinstance(card, Mapping) else card_id
        filename = f"{index + 1:02d}-{_safe_filename(player)}-{_safe_filename(card_label)}-forward.csv"
        items.append({
            "queue_position": index + 1,
            "player_id": player_id,
            "player": packet.get("player"),
            "card_id": card_id,
            "card_label": card.get("label") if isinstance(card, Mapping) else None,
            "decision": decision,
            "decision_as_of": decision_at.isoformat(),
            "minimum_horizon_days": int(policy.min_horizon_days),
            "horizon_end": horizon_end.isoformat(),
            "status": status,
            "sold_window_start": horizon_end.isoformat(),
            "sold_window_end": as_of_dt.isoformat(),
            "expected_export_filename": filename,
            "packet": dict(packet),
            "entry_collection": dict(entry_collection),
            "collection_instruction": (
                "In eBay Product Research, search the exact canonical card identity and export the complete sold result set "
                "for this forward window without hand-filtering. Preserve item ID, title, sold date, sold price, shipping, currency, and item URL."
            ),
        })

    return {
        "schema": OUTPUT_SCHEMA,
        "as_of": as_of_dt.isoformat(),
        "input_count": len(rows),
        "mature_count": mature,
        "waiting_horizon_count": waiting,
        "ineligible_count": ineligible,
        "collection_ready": mature > 0,
        "items": items,
    }
