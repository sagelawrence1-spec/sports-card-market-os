"""Versioned, presentation-safe contracts for the Market OS interface."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from models import Signal


SCHEMA_VERSION = "market-scan.v1"
PUBLIC_ACTIONS = {"BUY", "ACCUMULATE", "HOLD", "TRIM", "SELL"}


def evidence_grade(diagnostics: Mapping[str, float]) -> str:
    """Grade evidence quality without using the engine's conviction score."""
    sales = diagnostics.get("sales_30d", 0)
    liquidity = diagnostics.get("liquidity_score", 0)
    dispersion = diagnostics.get("volatility_30d", 1)
    if sales >= 10 and liquidity >= 70 and dispersion <= 0.12:
        return "A"
    if sales >= 5 and liquidity >= 50 and dispersion <= 0.22:
        return "B"
    return "C"


def _card_title(signal: Signal, asset: Mapping[str, Any] | None) -> str:
    if not asset:
        return signal.player

    identity = " ".join(
        str(asset.get(key, "")).strip()
        for key in ("year", "manufacturer", "set", "player")
        if str(asset.get(key, "")).strip()
    )
    number = str(asset.get("card_number", "")).strip()
    parallel = str(asset.get("parallel", "")).strip()
    grade_company = str(asset.get("grade_company", "")).strip()
    grade = str(asset.get("grade", "")).strip()
    if number:
        identity += f" #{number}"
    if parallel and parallel.lower() != "base":
        identity += f" · {parallel}"
    if grade_company and grade:
        identity += f" · {grade_company} {grade}"
    return identity


def build_market_scan(
    signals: Iterable[Signal],
    *,
    source_kind: str,
    source_label: str,
    universe_size: int,
    asset_lookup: Mapping[str, Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Translate engine signals into the stable contract consumed by the UI.

    WATCH and AVOID remain visible as engine classifications but are never
    promoted into user-facing capital actions.
    """
    lookup = asset_lookup or {}
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    items = []

    for signal in signals:
        diagnostics = signal.diagnostics
        fair_value = diagnostics.get("avg_price_30d", 0)
        action = signal.signal if signal.signal in PUBLIC_ACTIONS else None
        items.append(
            {
                "observation_id": signal.observation_id,
                "card_id": signal.card_id,
                "sport": signal.sport,
                "player": signal.player,
                "card": _card_title(signal, lookup.get(signal.card_id)),
                "action": action,
                "engine_classification": signal.signal,
                "alerts": signal.alerts,
                "confidence": signal.confidence,
                "evidence_grade": evidence_grade(diagnostics),
                "fair_value": round(fair_value, 2) if fair_value > 0 else None,
                "move_30d": round(diagnostics.get("price_change_30d", 0), 4),
                "liquidity_score": round(diagnostics.get("liquidity_score", 0), 1),
                "accepted_sales_30d": int(diagnostics.get("sales_30d", 0)),
                "thesis": signal.thesis,
            }
        )

    priority = {"BUY": 5, "SELL": 5, "ACCUMULATE": 4, "TRIM": 4, "HOLD": 2}
    items.sort(
        key=lambda item: (
            item["action"] is not None,
            "AOA" in item["alerts"],
            priority.get(item["action"], 0),
            item["confidence"],
        ),
        reverse=True,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "source": {"kind": source_kind, "label": source_label},
        "universe_size": universe_size,
        "items": items,
    }
