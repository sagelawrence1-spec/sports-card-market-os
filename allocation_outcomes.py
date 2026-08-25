"""Deterministic outcome grading for immutable capital-allocation decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
from statistics import median
from typing import Iterable

from allocation_audit import AllocationDecision


SCHEMA_VERSION = "allocation-outcomes.v1"


@dataclass(frozen=True)
class AllocationOutcome:
    run_id: str
    card_id: str
    realized_at: str
    realized_proceeds: float

    def validate(self) -> None:
        for name, value in (("run_id", self.run_id), ("card_id", self.card_id)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-blank text")
        _parse_timestamp(self.realized_at, "realized_at")
        if isinstance(self.realized_proceeds, bool) or not isinstance(self.realized_proceeds, (int, float)):
            raise ValueError("realized_proceeds must be numeric")
        proceeds = float(self.realized_proceeds)
        if not math.isfinite(proceeds) or proceeds < 0:
            raise ValueError("realized_proceeds must be finite and non-negative")


@dataclass(frozen=True)
class AllocationOutcomePolicy:
    exit_fee_rate: float = 0.0
    grade_a_min: float = 0.20
    grade_b_min: float = 0.10
    grade_c_min: float = 0.0
    grade_d_min: float = -0.10

    def validate(self) -> None:
        if isinstance(self.exit_fee_rate, bool) or not isinstance(self.exit_fee_rate, (int, float)):
            raise ValueError("exit_fee_rate must be numeric")
        fee = float(self.exit_fee_rate)
        if not math.isfinite(fee) or not 0.0 <= fee <= 1.0:
            raise ValueError("exit_fee_rate must be finite and between 0 and 1")
        thresholds = []
        for name in ("grade_a_min", "grade_b_min", "grade_c_min", "grade_d_min"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be numeric")
            value = float(value)
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
            thresholds.append(value)
        if thresholds != sorted(thresholds, reverse=True):
            raise ValueError("grade thresholds must descend from A through D")


def _parse_timestamp(raw: str, name: str) -> datetime:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{name} must be a non-blank ISO timestamp")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid ISO timestamp") from exc
    return parsed


def _decision_key(run_id: str, card_id: str) -> tuple[str, str]:
    return (run_id.strip(), card_id.strip())


def _letter_grade(score: float, policy: AllocationOutcomePolicy) -> str:
    if score >= policy.grade_a_min:
        return "A"
    if score >= policy.grade_b_min:
        return "B"
    if score >= policy.grade_c_min:
        return "C"
    if score >= policy.grade_d_min:
        return "D"
    return "F"


def grade_allocation(
    decision: AllocationDecision,
    outcome: AllocationOutcome,
    *,
    policy: AllocationOutcomePolicy | None = None,
) -> dict:
    """Grade one deployed allocation against realized capital proceeds."""
    policy = policy or AllocationOutcomePolicy()
    policy.validate()
    outcome.validate()

    if _decision_key(decision.run_id, decision.card_id) != _decision_key(outcome.run_id, outcome.card_id):
        raise ValueError("allocation outcome does not match decision identity")
    if not decision.ready or float(decision.approved_allocation) <= 0:
        raise ValueError("only deployed ready allocations can be outcome-graded")
    decided_at = _parse_timestamp(decision.decided_at, "decided_at")
    realized_at = _parse_timestamp(outcome.realized_at, "realized_at")
    if realized_at < decided_at:
        raise ValueError("allocation outcome predates the allocation decision")

    deployed = float(decision.approved_allocation)
    gross_proceeds = float(outcome.realized_proceeds)
    net_proceeds = gross_proceeds * (1.0 - float(policy.exit_fee_rate))
    realized_return = (net_proceeds - deployed) / deployed

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": decision.run_id,
        "card_id": decision.card_id,
        "decided_at": decision.decided_at,
        "realized_at": outcome.realized_at,
        "deployed_capital": deployed,
        "gross_realized_proceeds": gross_proceeds,
        "net_realized_proceeds": net_proceeds,
        "realized_return": realized_return,
        "pnl": net_proceeds - deployed,
        "grade": _letter_grade(realized_return, policy),
        "hit": realized_return >= 0.0,
        "evidence_grade": decision.evidence_grade,
        "confidence": decision.confidence,
        "action": decision.action,
        "cost_basis": "approved_allocation_vs_realized_proceeds_after_exit_fees",
    }


def grade_allocation_journal(
    decisions: Iterable[AllocationDecision],
    outcomes: Iterable[AllocationOutcome],
    *,
    policy: AllocationOutcomePolicy | None = None,
) -> dict:
    """Grade a journal without double-weighting decisions or accepting orphan outcomes."""
    policy = policy or AllocationOutcomePolicy()
    policy.validate()

    decision_by_key: dict[tuple[str, str], AllocationDecision] = {}
    for decision in decisions:
        key = _decision_key(decision.run_id, decision.card_id)
        if not all(key):
            raise ValueError("allocation decision identity must be non-blank")
        if key in decision_by_key:
            raise ValueError("duplicate allocation decision packet")
        decision_by_key[key] = decision

    outcome_by_key: dict[tuple[str, str], AllocationOutcome] = {}
    for outcome in outcomes:
        outcome.validate()
        key = _decision_key(outcome.run_id, outcome.card_id)
        if key in outcome_by_key:
            raise ValueError("duplicate allocation outcome packet")
        if key not in decision_by_key:
            raise ValueError("orphan allocation outcome has no journaled decision")
        outcome_by_key[key] = outcome

    eligible = {
        key: decision
        for key, decision in decision_by_key.items()
        if decision.ready and float(decision.approved_allocation) > 0
    }
    rows = [
        grade_allocation(decision, outcome_by_key[key], policy=policy)
        for key, decision in eligible.items()
        if key in outcome_by_key
    ]
    rows.sort(key=lambda row: (row["decided_at"], row["run_id"], row["card_id"]))

    returns = [float(row["realized_return"]) for row in rows]
    deployed = sum(float(row["deployed_capital"]) for row in rows)
    pnl = sum(float(row["pnl"]) for row in rows)
    grades = {grade: 0 for grade in "ABCDF"}
    for row in rows:
        grades[row["grade"]] += 1

    packet = {
        "schema_version": SCHEMA_VERSION,
        "eligible_allocations": len(eligible),
        "graded_allocations": len(rows),
        "unsettled_allocations": len(eligible) - len(rows),
        "deployed_capital": deployed,
        "realized_pnl": pnl,
        "portfolio_return": (pnl / deployed) if deployed > 0 else None,
        "hit_rate": (sum(int(row["hit"]) for row in rows) / len(rows)) if rows else None,
        "median_realized_return": float(median(returns)) if returns else None,
        "grades": grades,
        "outcomes": rows,
        "policy": {
            "exit_fee_rate": policy.exit_fee_rate,
            "grade_a_min": policy.grade_a_min,
            "grade_b_min": policy.grade_b_min,
            "grade_c_min": policy.grade_c_min,
            "grade_d_min": policy.grade_d_min,
        },
    }
    canonical = json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    packet["packet_sha256"] = hashlib.sha256(canonical).hexdigest()
    return packet
