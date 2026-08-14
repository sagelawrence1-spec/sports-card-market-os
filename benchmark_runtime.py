"""Runtime integration for leakage-safe benchmark journaling."""

from __future__ import annotations

from typing import Any, Mapping

from benchmark_cost_resolver import resolve_benchmark_cost_assumptions
from benchmark_journal import sync_contract_benchmark
from intelligence_benchmark import IntelligenceBenchmarkStore


def sync_benchmark_if_trustworthy(
    database_path: str,
    contract: Mapping[str, Any],
    *,
    horizon_days: int,
) -> dict[str, Any]:
    """Journal benchmark observations only when cost assumptions are trustworthy.

    A missing/partial cost context must not block the core market scan. Instead,
    benchmark capture is explicitly skipped and the blockers are returned for
    provenance and operational visibility.
    """
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive.")

    costs = resolve_benchmark_cost_assumptions(contract)
    if not costs["ready"]:
        return {
            "status": "skipped",
            "reason": "untrusted_cost_assumptions",
            "source": costs.get("source"),
            "blockers": list(costs.get("blockers") or []),
            "recorded": 0,
            "settled": 0,
        }

    summary = sync_contract_benchmark(
        IntelligenceBenchmarkStore(database_path),
        contract,
        horizon_days=horizon_days,
        exit_fee_rate=float(costs["exit_fee_rate"]),
        liquidity_haircut_rate=float(costs["liquidity_haircut_rate"]),
    )
    return {
        "status": "recorded",
        "reason": None,
        "source": costs["source"],
        "blockers": list(costs.get("blockers") or []),
        "exit_fee_rate": float(costs["exit_fee_rate"]),
        "liquidity_haircut_rate": float(costs["liquidity_haircut_rate"]),
        "recorded": int(summary.get("recorded", 0)),
        "settled": int(summary.get("settled", 0)),
    }
