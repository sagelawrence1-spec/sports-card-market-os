from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
import statistics
from typing import Any, Mapping

from intelligence_benchmark import BenchmarkObservation, IntelligenceBenchmarkStore


def _day(value: str) -> date:
    return datetime.fromisoformat(str(value)[:10]).date()


def _accepted_prices(item: Mapping[str, Any]) -> list[dict[str, Any]]:
    ledger=(item.get("evidence_ledger") or {}).get("accepted") or []
    rows=[]
    for row in ledger:
        if not row.get("used_in_valuation"):
            continue
        if str(row.get("currency") or "").upper()!="USD":
            continue
        price=row.get("price")
        event_date=row.get("event_date")
        if price is None or not event_date:
            continue
        try:
            price=float(price)
            sold=_day(event_date)
        except (TypeError,ValueError):
            continue
        if price<=0:
            continue
        rows.append({"price":price,"event_date":sold})
    return rows


def record_contract_observations(
    store: IntelligenceBenchmarkStore,
    contract: Mapping[str, Any],
    *,
    horizon_days: int=30,
    exit_fee_rate: float=0.0,
    liquidity_haircut_rate: float=0.0,
) -> int:
    """Persist point-in-time forecasts from a published market contract.

    The simple baseline is the median of the exact sold rows used in valuation. The
    intelligence estimate is the published fair value. Current price is the most
    recent accepted sold observation available at the time of the scan.
    """
    recorded=0
    for item in contract.get("items") or []:
        fair_value=item.get("fair_value")
        if fair_value is None:
            continue
        rows=_accepted_prices(item)
        if not rows:
            continue
        as_of=_day(item.get("last_updated") or contract.get("generated_at") or date.today().isoformat())
        latest=max(rows,key=lambda row:row["event_date"])
        confidence=float(item.get("confidence") or 0.0)
        if confidence>1:
            confidence/=100.0
        observation=BenchmarkObservation(
            card_id=str(item["card_id"]),
            as_of_date=as_of,
            horizon_days=int(horizon_days),
            current_price=latest["price"],
            baseline_estimate=float(statistics.median(row["price"] for row in rows)),
            intelligence_estimate=float(fair_value),
            evidence_grade=item.get("evidence_grade"),
            confidence=max(0.0,min(1.0,confidence)),
            exit_fee_rate=float(exit_fee_rate),
            liquidity_haircut_rate=float(liquidity_haircut_rate),
        )
        store.upsert_observation(observation)
        recorded+=1
    return recorded


def settle_matured_observations(
    store: IntelligenceBenchmarkStore,
    contract: Mapping[str, Any],
) -> int:
    """Settle matured forecasts only from accepted sold evidence after the horizon.

    The earliest accepted valuation-eligible USD sale on or after horizon end is the
    realized observation. Pre-horizon sales are never eligible, preserving the
    benchmark's leakage-safe full-horizon rule.
    """
    items={str(item.get("card_id")):item for item in contract.get("items") or []}
    settled=0
    for observation in store.load_observations():
        if observation.realized_price is not None:
            continue
        item=items.get(observation.card_id)
        if item is None:
            continue
        evaluation_date=_day(item.get("last_updated") or contract.get("generated_at") or date.today().isoformat())
        if observation.horizon_end>evaluation_date:
            continue
        candidates=[
            row for row in _accepted_prices(item)
            if observation.horizon_end<=row["event_date"]<=evaluation_date
        ]
        if not candidates:
            continue
        earliest=min(row["event_date"] for row in candidates)
        same_day=[row["price"] for row in candidates if row["event_date"]==earliest]
        realized=float(statistics.median(same_day))
        store.upsert_observation(replace(
            observation,
            realized_price=realized,
            realized_at=earliest,
        ))
        settled+=1
    return settled


def sync_contract_benchmark(
    store: IntelligenceBenchmarkStore,
    contract: Mapping[str, Any],
    *,
    horizon_days: int=30,
    exit_fee_rate: float=0.0,
    liquidity_haircut_rate: float=0.0,
) -> dict[str,int]:
    settled=settle_matured_observations(store,contract)
    recorded=record_contract_observations(
        store,
        contract,
        horizon_days=horizon_days,
        exit_fee_rate=exit_fee_rate,
        liquidity_haircut_rate=liquidity_haircut_rate,
    )
    return {"recorded":recorded,"settled":settled}
