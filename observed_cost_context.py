"""Observed transaction-cost and liquidity assumptions for benchmark grading."""

from __future__ import annotations

from dataclasses import dataclass
import statistics
from typing import Any, Mapping


@dataclass(frozen=True)
class CostContextPolicy:
    min_fee_samples: int = 5
    min_liquidity_samples: int = 5
    max_fee_rate: float = 0.30
    max_liquidity_haircut: float = 0.50

    def __post_init__(self) -> None:
        if self.min_fee_samples < 1 or self.min_liquidity_samples < 1:
            raise ValueError("sample floors must be positive")
        if not 0 <= self.max_fee_rate <= 1:
            raise ValueError("max_fee_rate must be between 0 and 1")
        if not 0 <= self.max_liquidity_haircut <= 1:
            raise ValueError("max_liquidity_haircut must be between 0 and 1")


def _accepted_rows(contract: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for item in contract.get("items") or []:
        for row in (item.get("evidence_ledger") or {}).get("accepted") or []:
            if not row.get("used_in_valuation"):
                continue
            if str(row.get("currency") or "").upper() != "USD":
                continue
            rows.append(row)
    return rows


def _safe_rate(value: Any, *, ceiling: float) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not 0 <= number <= ceiling:
        return None
    return number


def derive_observed_cost_context(
    contract: Mapping[str, Any],
    *,
    policy: CostContextPolicy | None = None,
) -> dict[str, Any]:
    """Derive benchmark assumptions only from explicit accepted evidence metadata."""
    policy = policy or CostContextPolicy()
    fee_rates: list[float] = []
    liquidity_rates: list[float] = []
    rejected_values = 0

    for row in _accepted_rows(contract):
        fee_raw = row.get("seller_fee_rate")
        liquidity_raw = row.get("liquidity_haircut_rate")

        if fee_raw is not None:
            parsed = _safe_rate(fee_raw, ceiling=policy.max_fee_rate)
            if parsed is None:
                rejected_values += 1
            else:
                fee_rates.append(parsed)

        if liquidity_raw is not None:
            parsed = _safe_rate(
                liquidity_raw,
                ceiling=policy.max_liquidity_haircut,
            )
            if parsed is None:
                rejected_values += 1
            else:
                liquidity_rates.append(parsed)

    blockers: list[str] = []
    if len(fee_rates) < policy.min_fee_samples:
        blockers.append("insufficient_fee_samples")
    if len(liquidity_rates) < policy.min_liquidity_samples:
        blockers.append("insufficient_liquidity_samples")

    return {
        "ready": not blockers,
        "blockers": blockers,
        "fee_samples": len(fee_rates),
        "liquidity_samples": len(liquidity_rates),
        "exit_fee_rate": (
            float(statistics.median(fee_rates))
            if len(fee_rates) >= policy.min_fee_samples
            else None
        ),
        "liquidity_haircut_rate": (
            float(statistics.median(liquidity_rates))
            if len(liquidity_rates) >= policy.min_liquidity_samples
            else None
        ),
        "rejected_values": rejected_values,
    }


def benchmark_cost_assumptions(
    contract: Mapping[str, Any],
    *,
    policy: CostContextPolicy | None = None,
) -> tuple[float, float]:
    """Return benchmark assumptions or fail closed when observed context is weak."""
    context = derive_observed_cost_context(contract, policy=policy)
    if not context["ready"]:
        raise RuntimeError(
            "Observed transaction-cost context is not ready: "
            + ", ".join(context["blockers"])
        )
    return (
        float(context["exit_fee_rate"]),
        float(context["liquidity_haircut_rate"]),
    )
