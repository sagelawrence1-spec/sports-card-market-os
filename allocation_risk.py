"""Candidate-specific liquidity and downside controls for approved allocations."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping


@dataclass(frozen=True)
class AllocationRiskProfile:
    card_id: str
    liquidity_score: float
    downside_pct: float

    def __post_init__(self) -> None:
        if not isinstance(self.card_id, str) or not self.card_id.strip():
            raise ValueError("card_id must be non-blank text")
        for name, value in (
            ("liquidity_score", self.liquidity_score),
            ("downside_pct", self.downside_pct),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be numeric")
            numeric = float(value)
            if not math.isfinite(numeric) or not 0 <= numeric <= 1:
                raise ValueError(f"{name} must be finite and between 0 and 1")

    @property
    def multiplier(self) -> float:
        return float(self.liquidity_score) * (1.0 - float(self.downside_pct))


def apply_candidate_risk(
    allocations: list[Mapping[str, Any]],
    risk_by_card: Mapping[str, AllocationRiskProfile],
    *,
    portfolio_value: float,
) -> list[dict[str, Any]]:
    """Haircut approved sizing for candidate liquidity/downside; never increase it."""
    if isinstance(portfolio_value, bool) or not isinstance(portfolio_value, (int, float)):
        raise ValueError("portfolio_value must be a finite positive number")
    portfolio_value = float(portfolio_value)
    if not math.isfinite(portfolio_value) or portfolio_value <= 0:
        raise ValueError("portfolio_value must be a finite positive number")

    results: list[dict[str, Any]] = []
    for raw in allocations:
        row = dict(raw)
        requested = float(row.get("allocation") or 0.0)
        if not row.get("ready") or requested <= 0:
            row["risk_adjusted_allocation"] = 0.0
            row["risk_adjusted_allocation_pct"] = 0.0
            row["risk_blockers"] = list(row.get("blockers") or [])
            results.append(row)
            continue

        card_id = str(row.get("card_id") or "").strip()
        profile = risk_by_card.get(card_id)
        if profile is None:
            row["risk_adjusted_allocation"] = 0.0
            row["risk_adjusted_allocation_pct"] = 0.0
            row["risk_blockers"] = ["missing_candidate_risk_profile"]
            results.append(row)
            continue

        adjusted = round(min(requested, requested * profile.multiplier), 2)
        blockers: list[str] = []
        if profile.liquidity_score <= 0:
            blockers.append("no_liquidity_capacity")
        if profile.downside_pct >= 1:
            blockers.append("total_downside_risk")

        row["risk_adjusted_allocation"] = adjusted
        row["risk_adjusted_allocation_pct"] = round(adjusted / portfolio_value, 6)
        row["risk_blockers"] = blockers
        row["liquidity_score"] = float(profile.liquidity_score)
        row["downside_pct"] = float(profile.downside_pct)
        row["risk_multiplier"] = round(profile.multiplier, 6)
        results.append(row)

    return results
