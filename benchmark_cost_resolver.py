"""Resolve benchmark transaction-cost assumptions without inventing placeholders."""

from __future__ import annotations

import os
from typing import Any, Mapping

from observed_cost_context import benchmark_cost_assumptions


def _explicit_env_fraction(name: str) -> float | None:
    raw = (os.getenv(name) or "").strip()
    if raw == "":
        return None
    value = float(raw)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1.")
    return value


def resolve_benchmark_cost_assumptions(
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Prefer observed evidence; allow only explicit env fallback.

    If neither observed evidence nor explicit configuration is sufficient, return
    a fail-closed result so benchmark capture can be skipped without blocking the
    market scan itself.
    """
    try:
        fee_rate, liquidity_rate = benchmark_cost_assumptions(contract)
        return {
            "ready": True,
            "source": "observed",
            "exit_fee_rate": fee_rate,
            "liquidity_haircut_rate": liquidity_rate,
            "blockers": [],
        }
    except RuntimeError as exc:
        observed_blocker = str(exc)

    fee_rate = _explicit_env_fraction("BENCHMARK_EXIT_FEE_RATE")
    liquidity_rate = _explicit_env_fraction("BENCHMARK_LIQUIDITY_HAIRCUT_RATE")
    blockers: list[str] = []
    if fee_rate is None:
        blockers.append("missing_explicit_exit_fee_rate")
    if liquidity_rate is None:
        blockers.append("missing_explicit_liquidity_haircut_rate")

    if blockers:
        return {
            "ready": False,
            "source": None,
            "exit_fee_rate": None,
            "liquidity_haircut_rate": None,
            "blockers": [observed_blocker, *blockers],
        }

    return {
        "ready": True,
        "source": "explicit_env",
        "exit_fee_rate": fee_rate,
        "liquidity_haircut_rate": liquidity_rate,
        "blockers": [observed_blocker],
    }
