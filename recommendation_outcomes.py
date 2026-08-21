"""Deterministic outcome grading for settled recommendation journal records."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from statistics import median
from typing import Iterable

from recommendation_journal import Recommendation


SCHEMA_VERSION = "recommendation-outcomes.v1"
_DIRECTIONAL_LONG = {"BUY", "ACCUMULATE"}
_DIRECTIONAL_SHORT = {"TRIM", "SELL"}
_SUPPORTED_ACTIONS = _DIRECTIONAL_LONG | _DIRECTIONAL_SHORT | {"HOLD"}


@dataclass(frozen=True)
class OutcomePolicy:
    exit_fee_rate: float = 0.0
    liquidity_haircut_rate: float = 0.0
    hold_tolerance_pct: float = 0.05
    grade_a_min: float = 0.20
    grade_b_min: float = 0.10
    grade_c_min: float = 0.0
    grade_d_min: float = -0.10

    def validate(self) -> None:
        for name in ("exit_fee_rate", "liquidity_haircut_rate"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if not 0.0 <= float(self.hold_tolerance_pct) <= 1.0:
            raise ValueError("hold_tolerance_pct must be between 0 and 1")
        thresholds = [
            float(self.grade_a_min),
            float(self.grade_b_min),
            float(self.grade_c_min),
            float(self.grade_d_min),
        ]
        if thresholds != sorted(thresholds, reverse=True):
            raise ValueError("grade thresholds must descend from A through D")


def _net_realized(rec: Recommendation, policy: OutcomePolicy) -> float:
    if rec.realized_price is None:
        raise ValueError("outcome grading requires a settled recommendation")
    return (
        float(rec.realized_price)
        * (1.0 - float(policy.exit_fee_rate))
        * (1.0 - float(policy.liquidity_haircut_rate))
    )


def _signed_return(rec: Recommendation, net_realized: float, policy: OutcomePolicy) -> float:
    if rec.entry_price <= 0:
        raise ValueError("entry_price must be positive")
    raw_return = (net_realized - float(rec.entry_price)) / float(rec.entry_price)
    action = str(rec.action).upper()
    if action in _DIRECTIONAL_LONG:
        return raw_return
    if action in _DIRECTIONAL_SHORT:
        return -raw_return
    if action == "HOLD":
        return float(policy.hold_tolerance_pct) - abs(raw_return)
    raise ValueError(f"unsupported recommendation action: {rec.action}")


def _letter_grade(score: float, policy: OutcomePolicy) -> str:
    if score >= policy.grade_a_min:
        return "A"
    if score >= policy.grade_b_min:
        return "B"
    if score >= policy.grade_c_min:
        return "C"
    if score >= policy.grade_d_min:
        return "D"
    return "F"


def _packet_sha256(packet: dict) -> str:
    canonical = json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def grade_recommendation(
    rec: Recommendation,
    *,
    policy: OutcomePolicy | None = None,
) -> dict:
    """Grade one matured recommendation using only realized post-horizon evidence."""
    policy = policy or OutcomePolicy()
    policy.validate()
    action = str(rec.action).upper()
    if action not in _SUPPORTED_ACTIONS:
        raise ValueError(f"unsupported recommendation action: {rec.action}")
    if rec.realized_price is None or rec.realized_at is None:
        raise ValueError("outcome grading requires a settled recommendation")
    if rec.realized_at < rec.horizon_end:
        raise ValueError("realized outcome predates the recommendation horizon")

    net_realized = _net_realized(rec, policy)
    score = _signed_return(rec, net_realized, policy)
    raw_return = (net_realized - float(rec.entry_price)) / float(rec.entry_price)
    fair_value_error = abs(float(rec.fair_value) - net_realized) / net_realized if net_realized else None

    return {
        "schema_version": SCHEMA_VERSION,
        "observation_id": rec.observation_id,
        "card_id": rec.card_id,
        "as_of_date": rec.as_of_date.isoformat(),
        "horizon_end": rec.horizon_end.isoformat(),
        "realized_at": rec.realized_at.isoformat(),
        "action": action,
        "entry_price": float(rec.entry_price),
        "fair_value": float(rec.fair_value),
        "realized_price": float(rec.realized_price),
        "net_realized_price": net_realized,
        "raw_net_return": raw_return,
        "action_adjusted_return": score,
        "fair_value_absolute_pct_error": fair_value_error,
        "grade": _letter_grade(score, policy),
        "hit": score >= 0.0,
        "cost_basis": "realized_after_exit_fees_and_liquidity_haircut",
    }


def grade_journal(
    recommendations: Iterable[Recommendation],
    *,
    policy: OutcomePolicy | None = None,
) -> dict:
    """Produce an auditable, cryptographically bound outcome packet."""
    policy = policy or OutcomePolicy()
    policy.validate()
    rows = [
        grade_recommendation(rec, policy=policy)
        for rec in recommendations
        if rec.realized_price is not None and rec.realized_at is not None
    ]
    rows.sort(key=lambda row: (row["as_of_date"], row["observation_id"]))

    by_grade = {grade: 0 for grade in "ABCDF"}
    by_action: dict[str, dict[str, float | int | None]] = {}
    for row in rows:
        by_grade[row["grade"]] += 1
        block = by_action.setdefault(row["action"], {"settled": 0, "hits": 0, "returns": []})
        block["settled"] += 1
        block["hits"] += int(row["hit"])
        block["returns"].append(row["action_adjusted_return"])

    action_summary = {}
    for action, block in sorted(by_action.items()):
        settled = int(block["settled"])
        returns = list(block["returns"])
        action_summary[action] = {
            "settled": settled,
            "hit_rate": float(block["hits"]) / settled if settled else None,
            "median_action_adjusted_return": float(median(returns)) if returns else None,
        }

    returns = [row["action_adjusted_return"] for row in rows]
    packet = {
        "schema_version": SCHEMA_VERSION,
        "settled": len(rows),
        "hit_rate": (sum(int(row["hit"]) for row in rows) / len(rows)) if rows else None,
        "median_action_adjusted_return": float(median(returns)) if returns else None,
        "grades": by_grade,
        "actions": action_summary,
        "outcomes": rows,
        "policy": {
            "exit_fee_rate": policy.exit_fee_rate,
            "liquidity_haircut_rate": policy.liquidity_haircut_rate,
            "hold_tolerance_pct": policy.hold_tolerance_pct,
            "grade_a_min": policy.grade_a_min,
            "grade_b_min": policy.grade_b_min,
            "grade_c_min": policy.grade_c_min,
            "grade_d_min": policy.grade_d_min,
        },
    }
    packet["packet_sha256"] = _packet_sha256(packet)
    return packet
