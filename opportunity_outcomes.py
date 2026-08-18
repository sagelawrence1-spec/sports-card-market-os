"""Leakage-safe outcome grading for immutable Opportunity Engine decisions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

PACKET_SCHEMA = "opportunity-decision-packet.v1"
COLLECTION_SCHEMA = "opportunity-repricing-collection.v1"
OUTCOME_SCHEMA = "opportunity-outcome.v1"
_ACTIONABLE = {"START_POSITION", "ADD"}


@dataclass(frozen=True)
class OpportunityOutcomePolicy:
    min_horizon_days: int = 30
    exit_fee_rate: float = 0.0
    liquidity_haircut_rate: float = 0.0
    grade_a_min: float = 0.20
    grade_b_min: float = 0.10
    grade_c_min: float = 0.0
    grade_d_min: float = -0.10

    def validate(self) -> None:
        if int(self.min_horizon_days) < 1:
            raise ValueError("min_horizon_days must be at least 1")
        for name in ("exit_fee_rate", "liquidity_haircut_rate"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        thresholds = [
            float(self.grade_a_min),
            float(self.grade_b_min),
            float(self.grade_c_min),
            float(self.grade_d_min),
        ]
        if thresholds != sorted(thresholds, reverse=True):
            raise ValueError("grade thresholds must descend from A through D")


def _aware(value: Any, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _letter_grade(score: float, policy: OpportunityOutcomePolicy) -> str:
    if score >= policy.grade_a_min:
        return "A"
    if score >= policy.grade_b_min:
        return "B"
    if score >= policy.grade_c_min:
        return "C"
    if score >= policy.grade_d_min:
        return "D"
    return "F"


def grade_opportunity_decision(
    packet: Mapping[str, Any],
    collection: Mapping[str, Any],
    *,
    realized_price: float,
    realized_at: str,
    policy: OpportunityOutcomePolicy | None = None,
) -> dict[str, Any]:
    """Grade one actionable decision after a minimum forward horizon.

    Entry value is the authoritative post-catalyst median that was available at
    decision time. The grader refuses to reconstruct or substitute a later entry
    price, preventing hindsight from improving the original call.
    """
    policy = policy or OpportunityOutcomePolicy()
    policy.validate()

    if packet.get("schema") != PACKET_SCHEMA:
        raise ValueError("unsupported opportunity decision packet schema")
    if collection.get("schema") != COLLECTION_SCHEMA:
        raise ValueError("unsupported opportunity repricing collection schema")

    decision = str(packet.get("decision", "")).strip()
    if packet.get("actionable") is not True or decision not in _ACTIONABLE:
        raise ValueError("outcome grading currently requires an actionable START_POSITION or ADD decision")

    card = packet.get("card")
    card_id = str(card.get("card_id", "")).strip() if isinstance(card, Mapping) else ""
    player_id = str(packet.get("player_id", "")).strip()
    catalyst_at = str(packet.get("catalyst_at", "")).strip()
    as_of = str(packet.get("as_of", "")).strip()
    if not player_id or not card_id or not catalyst_at or not as_of:
        raise ValueError("decision packet identity is incomplete")

    if str(collection.get("player_id", "")).strip() != player_id:
        raise ValueError("repricing collection player does not match decision packet")
    if str(collection.get("card_id", "")).strip() != card_id:
        raise ValueError("repricing collection card does not match decision packet")

    verification = collection.get("verification")
    if not isinstance(verification, Mapping) or verification.get("verified") is not True:
        raise ValueError("outcome grading requires verified authoritative repricing evidence")
    if str(verification.get("catalyst_at", "")).strip() != catalyst_at:
        raise ValueError("repricing collection catalyst does not match decision packet")
    if str(verification.get("as_of", "")).strip() != as_of:
        raise ValueError("repricing collection as_of does not match decision packet")

    entry_price = float(verification.get("post_median") or 0.0)
    if entry_price <= 0.0:
        raise ValueError("verified repricing collection requires positive post_median entry price")
    realized_price = float(realized_price)
    if realized_price <= 0.0:
        raise ValueError("realized_price must be positive")

    decision_at = _aware(as_of, field="as_of")
    outcome_at = _aware(realized_at, field="realized_at")
    horizon_end = decision_at + timedelta(days=int(policy.min_horizon_days))
    if outcome_at < horizon_end:
        raise ValueError("realized outcome predates the minimum decision horizon")

    net_realized = (
        realized_price
        * (1.0 - float(policy.exit_fee_rate))
        * (1.0 - float(policy.liquidity_haircut_rate))
    )
    net_return = (net_realized - entry_price) / entry_price

    return {
        "schema": OUTCOME_SCHEMA,
        "player_id": player_id,
        "card_id": card_id,
        "catalyst_at": catalyst_at,
        "decision_as_of": as_of,
        "decision": decision,
        "entry_price": entry_price,
        "entry_price_basis": "authoritative_post_catalyst_median_available_at_decision_time",
        "realized_at": outcome_at.isoformat(),
        "realized_price": realized_price,
        "net_realized_price": net_realized,
        "net_return": net_return,
        "grade": _letter_grade(net_return, policy),
        "hit": net_return >= 0.0,
        "minimum_horizon_days": int(policy.min_horizon_days),
        "horizon_end": horizon_end.isoformat(),
        "cost_basis": "realized_after_exit_fees_and_liquidity_haircut",
        "policy": {
            "exit_fee_rate": policy.exit_fee_rate,
            "liquidity_haircut_rate": policy.liquidity_haircut_rate,
            "grade_a_min": policy.grade_a_min,
            "grade_b_min": policy.grade_b_min,
            "grade_c_min": policy.grade_c_min,
            "grade_d_min": policy.grade_d_min,
        },
    }
