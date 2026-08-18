"""Grade Opportunity Engine calls from authoritative forward Product Research comps."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path
from statistics import median
from typing import Any, Mapping

from entity_matcher import SportsCardEntityMatcher, build_ebay_query
from opportunity_outcomes import OpportunityOutcomePolicy, grade_opportunity_decision
from providers import EbayProductResearchProvider

AUTHORITATIVE_SOURCE = "EBAY_PRODUCT_RESEARCH"
OUTPUT_SCHEMA = "opportunity-authoritative-outcome.v1"


def _aware(value: Any, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _sold_day(value: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"Product Research sold date must be ISO day: {value}") from exc


def grade_authoritative_market_outcome(
    packet: Mapping[str, Any],
    entry_collection: Mapping[str, Any],
    *,
    asset: Mapping[str, Any],
    csv_path: str | Path,
    as_of: str,
    min_forward_comps: int = 3,
    policy: OpportunityOutcomePolicy | None = None,
) -> dict[str, Any]:
    """Grade one capital call from a forward authoritative sold-comp window.

    Product Research currently provides day-granularity sold dates. The exact
    minimum-horizon day and current ``as_of`` day are excluded rather than guessed.
    Only entity-matched sales strictly after the horizon and strictly before the
    cutoff contribute to the forward market median.
    """
    policy = policy or OpportunityOutcomePolicy()
    policy.validate()
    if int(min_forward_comps) < 1:
        raise ValueError("min_forward_comps must be at least 1")

    card = packet.get("card")
    card_id = str(card.get("card_id", "")).strip() if isinstance(card, Mapping) else ""
    player_id = str(packet.get("player_id", "")).strip()
    decision_as_of = str(packet.get("as_of", "")).strip()
    if not player_id or not card_id or not decision_as_of:
        raise ValueError("decision packet identity is incomplete")
    if str(asset.get("card_id", "")).strip() != card_id:
        raise ValueError("asset card_id must match decision packet")

    decision_at = _aware(decision_as_of, field="decision as_of")
    cutoff = _aware(as_of, field="as_of")
    horizon_start = decision_at + __import__("datetime").timedelta(days=int(policy.min_horizon_days))
    if cutoff <= horizon_start:
        raise ValueError("as_of must be after the minimum decision horizon")

    provider = EbayProductResearchProvider()
    query = build_ebay_query(dict(asset))
    result = provider.load_csv(str(csv_path), query=query)
    matcher = SportsCardEntityMatcher()

    prices: list[float] = []
    evidence_ids: list[str] = []
    accepted = review = rejected = 0
    excluded_horizon_day = excluded_as_of_day = excluded_outside_window = 0

    for record in result.records:
        decision = matcher.match(dict(asset), record.title)
        if not decision.accepted:
            if decision.reason == "manual_review":
                review += 1
            else:
                rejected += 1
            continue

        sold_day = _sold_day(record.event_date)
        if sold_day == horizon_start.date():
            excluded_horizon_day += 1
            continue
        if sold_day == cutoff.date():
            excluded_as_of_day += 1
            continue
        if sold_day < horizon_start.date() or sold_day > cutoff.date():
            excluded_outside_window += 1
            continue

        prices.append(float(record.price))
        evidence_ids.append(f"{record.provider}:{record.source_item_id}")
        accepted += 1

    if len(prices) < int(min_forward_comps):
        return {
            "schema": OUTPUT_SCHEMA,
            "player_id": player_id,
            "card_id": card_id,
            "graded": False,
            "blocking_reason": "insufficient_forward_authoritative_comps",
            "forward_count": len(prices),
            "minimum_forward_comps": int(min_forward_comps),
            "horizon_start": horizon_start.isoformat(),
            "as_of": cutoff.isoformat(),
            "query": query,
            "provider_metadata": result.metadata,
            "matching": {
                "accepted": accepted,
                "manual_review": review,
                "rejected": rejected,
                "excluded_horizon_day": excluded_horizon_day,
                "excluded_as_of_day": excluded_as_of_day,
                "excluded_outside_window": excluded_outside_window,
            },
            "evidence_ids": evidence_ids,
        }

    forward_median = float(median(prices))
    graded = grade_opportunity_decision(
        packet,
        entry_collection,
        realized_price=forward_median,
        realized_at=cutoff.isoformat(),
        policy=policy,
    )
    return {
        "schema": OUTPUT_SCHEMA,
        "player_id": player_id,
        "card_id": card_id,
        "graded": True,
        "blocking_reason": None,
        "forward_count": len(prices),
        "minimum_forward_comps": int(min_forward_comps),
        "forward_median": forward_median,
        "forward_price_basis": "authoritative_product_research_median_after_minimum_horizon",
        "horizon_start": horizon_start.isoformat(),
        "as_of": cutoff.isoformat(),
        "query": query,
        "provider_metadata": result.metadata,
        "matching": {
            "accepted": accepted,
            "manual_review": review,
            "rejected": rejected,
            "excluded_horizon_day": excluded_horizon_day,
            "excluded_as_of_day": excluded_as_of_day,
            "excluded_outside_window": excluded_outside_window,
        },
        "evidence_ids": evidence_ids,
        "outcome": graded,
    }
