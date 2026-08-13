"""Fail-closed capital allocation validation driven by realized recommendation outcomes."""

from __future__ import annotations

from dataclasses import dataclass
import statistics
from typing import Any

from recommendation_journal import Recommendation, RecommendationJournal


DEPLOY_ACTIONS = {"BUY", "ACCUMULATE"}


def confidence_band(confidence: float) -> str:
    if confidence >= 0.80:
        return "high"
    if confidence >= 0.65:
        return "medium"
    return "low"


def signed_return(row: Recommendation) -> float:
    if row.realized_price is None:
        raise ValueError("Outcome must be settled before grading.")
    raw = (row.realized_price - row.entry_price) / row.entry_price
    return -raw if row.action in {"TRIM", "SELL"} else raw


@dataclass(frozen=True)
class AllocationPolicy:
    min_overall_settled: int = 20
    min_action_settled: int = 8
    min_segment_settled: int = 5
    min_hit_rate: float = 0.55
    min_median_return: float = 0.02
    max_position_pct: float = 0.10
    max_total_deployment_pct: float = 0.50

    def __post_init__(self) -> None:
        if self.min_overall_settled < 1:
            raise ValueError("min_overall_settled must be positive.")
        if self.min_action_settled < 1 or self.min_segment_settled < 1:
            raise ValueError("sample floors must be positive.")
        if not 0 <= self.min_hit_rate <= 1:
            raise ValueError("min_hit_rate must be between 0 and 1.")
        if not 0 <= self.max_position_pct <= 1:
            raise ValueError("max_position_pct must be between 0 and 1.")
        if not 0 <= self.max_total_deployment_pct <= 1:
            raise ValueError("max_total_deployment_pct must be between 0 and 1.")
        if self.max_position_pct > self.max_total_deployment_pct:
            raise ValueError("position cap cannot exceed deployment cap.")


@dataclass(frozen=True)
class AllocationCandidate:
    card_id: str
    action: str
    entry_price: float
    fair_value: float
    confidence: float
    evidence_grade: str

    @property
    def upside(self) -> float:
        if self.entry_price <= 0:
            return 0.0
        return (self.fair_value - self.entry_price) / self.entry_price


def _settled_deploy_rows(journal: RecommendationJournal) -> list[Recommendation]:
    return [
        row
        for row in journal.load()
        if row.realized_price is not None and row.action in DEPLOY_ACTIONS
    ]


def _metrics(rows: list[Recommendation]) -> dict[str, Any]:
    if not rows:
        return {"settled": 0, "hit_rate": None, "median_return": None}
    returns = [signed_return(row) for row in rows]
    return {
        "settled": len(rows),
        "hit_rate": sum(value > 0 for value in returns) / len(returns),
        "median_return": float(statistics.median(returns)),
    }


def allocation_readiness(
    journal: RecommendationJournal,
    candidate: AllocationCandidate,
    *,
    policy: AllocationPolicy | None = None,
) -> dict[str, Any]:
    """Require realized proof before allowing new capital to be deployed."""
    policy = policy or AllocationPolicy()
    blockers: list[str] = []

    if candidate.action not in DEPLOY_ACTIONS:
        blockers.append("non_deploy_action")
    if candidate.entry_price <= 0 or candidate.fair_value <= 0:
        blockers.append("invalid_price")
    if candidate.upside <= 0:
        blockers.append("no_positive_upside")

    all_rows = _settled_deploy_rows(journal)
    action_rows = [row for row in all_rows if row.action == candidate.action]
    band = confidence_band(candidate.confidence)
    segment_rows = [
        row
        for row in action_rows
        if row.evidence_grade == candidate.evidence_grade
        and confidence_band(row.confidence) == band
    ]

    views = {
        "overall": (_metrics(all_rows), policy.min_overall_settled),
        "action": (_metrics(action_rows), policy.min_action_settled),
        "segment": (_metrics(segment_rows), policy.min_segment_settled),
    }

    for name, (metrics, sample_floor) in views.items():
        if metrics["settled"] < sample_floor:
            blockers.append(f"{name}_sample_too_small")
            continue
        if metrics["hit_rate"] is None or metrics["hit_rate"] < policy.min_hit_rate:
            blockers.append(f"{name}_hit_rate_below_floor")
        if (
            metrics["median_return"] is None
            or metrics["median_return"] < policy.min_median_return
        ):
            blockers.append(f"{name}_median_return_below_floor")

    return {
        "ready": not blockers,
        "blockers": blockers,
        "confidence_band": band,
        "overall": views["overall"][0],
        "action": views["action"][0],
        "segment": views["segment"][0],
    }


def size_candidates(
    journal: RecommendationJournal,
    candidates: list[AllocationCandidate],
    *,
    portfolio_value: float,
    policy: AllocationPolicy | None = None,
) -> list[dict[str, Any]]:
    """Return capped proposed allocations; never deploy to an unproven segment."""
    policy = policy or AllocationPolicy()
    if portfolio_value <= 0:
        raise ValueError("portfolio_value must be positive.")

    approved: list[tuple[AllocationCandidate, dict[str, Any], float]] = []
    rejected: list[dict[str, Any]] = []

    for candidate in candidates:
        readiness = allocation_readiness(journal, candidate, policy=policy)
        if not readiness["ready"]:
            rejected.append({
                "card_id": candidate.card_id,
                "action": candidate.action,
                "allocation": 0.0,
                "allocation_pct": 0.0,
                "ready": False,
                "blockers": readiness["blockers"],
            })
            continue

        evidence_weight = {"A": 1.0, "B": 0.85, "C": 0.65}.get(
            candidate.evidence_grade, 0.50
        )
        score = max(candidate.upside, 0.0) * candidate.confidence * evidence_weight
        approved.append((candidate, readiness, score))

    if not approved:
        return rejected

    score_total = sum(score for _, _, score in approved)
    deployment_cap = portfolio_value * policy.max_total_deployment_pct
    position_cap = portfolio_value * policy.max_position_pct

    allocations: list[dict[str, Any]] = []
    remaining = deployment_cap

    for candidate, readiness, score in sorted(
        approved, key=lambda item: item[2], reverse=True
    ):
        proportional = deployment_cap * (score / score_total) if score_total else 0.0
        amount = min(proportional, position_cap, remaining)
        remaining -= amount
        allocations.append({
            "card_id": candidate.card_id,
            "action": candidate.action,
            "allocation": round(amount, 2),
            "allocation_pct": round(amount / portfolio_value, 6),
            "ready": True,
            "blockers": [],
            "upside": round(candidate.upside, 6),
            "confidence": candidate.confidence,
            "evidence_grade": candidate.evidence_grade,
            "track_record": {
                "overall": readiness["overall"],
                "action": readiness["action"],
                "segment": readiness["segment"],
            },
        })

    return allocations + rejected
