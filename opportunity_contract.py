"""Presentation-safe contract for the Opportunity Radar."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from opportunity_engine import OpportunityStage, OpportunityThesis

SCHEMA_VERSION = "opportunity-radar.v1"

_STAGE_PRIORITY = {
    OpportunityStage.ENTRY: 5,
    OpportunityStage.ACCELERATION: 4,
    OpportunityStage.PRE_CATALYST: 3,
    OpportunityStage.CONSENSUS: 2,
    OpportunityStage.BROKEN: 0,
}


def build_opportunity_radar(
    theses: Iterable[OpportunityThesis],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    items = []
    for thesis in theses:
        items.append(
            {
                "thesis_id": thesis.thesis_id,
                "player_id": thesis.player_id,
                "player": thesis.player,
                "sport": thesis.sport,
                "type": thesis.opportunity_type.value,
                "stage": thesis.stage.value,
                "action": thesis.recommended_action.value,
                "headline": thesis.headline,
                "why_now": thesis.why_now,
                "evidence_confidence": thesis.evidence_confidence,
                "edge_conviction": thesis.edge_conviction,
                "asymmetry_rating": thesis.asymmetry_rating,
                "max_position_size": thesis.max_position_size,
                "card_targets": [target.to_dict() for target in thesis.card_targets],
                "next_confirmation_events": list(thesis.next_confirmation_events),
                "kill_conditions": list(thesis.kill_conditions),
                "created_at": thesis.created_at,
                "updated_at": thesis.last_updated_at,
            }
        )
    items.sort(
        key=lambda item: (
            _STAGE_PRIORITY[OpportunityStage(item["stage"])],
            item["edge_conviction"],
            item["asymmetry_rating"],
        ),
        reverse=True,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "items": items,
    }
