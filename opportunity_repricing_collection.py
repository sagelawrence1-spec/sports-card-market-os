"""Turn authoritative Product Research exports into leakage-safe repricing evidence."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Mapping

from entity_matcher import SportsCardEntityMatcher, build_ebay_query
from opportunity_pricing import OpportunityPriceComp, RepricingVerification, verify_repricing
from providers import EbayProductResearchProvider

AUTHORITATIVE_SOURCE = "EBAY_PRODUCT_RESEARCH"


def _aware(value: str, *, field: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _sold_day(value: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"Product Research sold date must be ISO day: {value}") from exc


def collect_repricing_verification(
    request: Mapping[str, Any],
    *,
    asset: Mapping[str, Any],
    csv_path: str | Path,
) -> dict[str, Any]:
    """Load one Product Research export, entity-match it, and verify repricing.

    Product Research sold dates are day-granularity in the current authoritative
    adapter. Rows on the catalyst calendar day cannot safely be classified as before
    or after the catalyst timestamp, and rows on the current ``as_of`` calendar day
    may have occurred after the point-in-time cutoff. Both boundary days are excluded
    rather than guessed.
    """
    if request.get("source_type") != AUTHORITATIVE_SOURCE:
        raise ValueError("repricing request must require EBAY_PRODUCT_RESEARCH")

    card_id = str(request.get("card_id", "")).strip()
    asset_card_id = str(asset.get("card_id", "")).strip()
    if not card_id or asset_card_id != card_id:
        raise ValueError("asset card_id must match repricing request")

    catalyst_at = str(request.get("catalyst_at", ""))
    as_of = str(request.get("as_of", ""))
    catalyst = _aware(catalyst_at, field="catalyst_at")
    cutoff = _aware(as_of, field="as_of")
    if cutoff < catalyst:
        raise ValueError("as_of cannot precede catalyst_at")

    provider = EbayProductResearchProvider()
    query = build_ebay_query(dict(asset))
    result = provider.load_csv(str(csv_path), query=query)
    matcher = SportsCardEntityMatcher()

    comps: list[OpportunityPriceComp] = []
    accepted = review = rejected = 0
    ambiguous_catalyst_day = ambiguous_as_of_day = 0
    for record in result.records:
        decision = matcher.match(dict(asset), record.title)
        if not decision.accepted:
            if decision.reason == "manual_review":
                review += 1
            else:
                rejected += 1
            continue

        sold_day = _sold_day(record.event_date)
        if sold_day == catalyst.date():
            ambiguous_catalyst_day += 1
            continue
        if sold_day == cutoff.date():
            ambiguous_as_of_day += 1
            continue

        # Midday UTC is only a transport timestamp. Because boundary dates are
        # excluded, the day is unambiguously before/after the catalyst and cutoff.
        sold_at = datetime.combine(sold_day, time(12, 0), tzinfo=timezone.utc).isoformat()
        comps.append(
            OpportunityPriceComp(
                # Product Research can report separate purchases from one
                # multi-quantity listing. Day granularity is the strongest stable
                # transaction key currently available, so bind evidence identity to
                # provider + item ID + sold date rather than item ID alone.
                evidence_id=f"{record.provider}:{record.source_item_id}:{record.event_date}",
                card_id=card_id,
                sold_at=sold_at,
                landed_price=float(record.price),
                source_type=AUTHORITATIVE_SOURCE,
            )
        )
        accepted += 1

    verification: RepricingVerification = verify_repricing(
        card_id=card_id,
        catalyst_at=catalyst_at,
        as_of=as_of,
        comps=comps,
        min_pre_comps=int(request.get("min_pre_comps", 3)),
        min_post_comps=int(request.get("min_post_comps", 3)),
        pre_window_days=max(1, (catalyst - _aware(str(request["pre_start"]), field="pre_start")).days),
        post_window_days=max(1, (_aware(str(request["post_window_end"]), field="post_window_end") - catalyst).days),
    )

    return {
        "schema": "opportunity-repricing-collection.v1",
        "player_id": request.get("player_id"),
        "card_id": card_id,
        "query": query,
        "csv_path": str(csv_path),
        "provider_metadata": result.metadata,
        "matching": {
            "accepted": accepted,
            "manual_review": review,
            "rejected": rejected,
            "excluded_ambiguous_catalyst_day": ambiguous_catalyst_day,
            "excluded_ambiguous_as_of_day": ambiguous_as_of_day,
        },
        "verification": {
            "schema": verification.schema,
            "verified": verification.verified,
            "blocking_reason": verification.blocking_reason,
            "pre_count": verification.pre_count,
            "post_count": verification.post_count,
            "pre_median": verification.pre_median,
            "post_median": verification.post_median,
            "repricing_pct": verification.repricing_pct,
            "evidence_ids": list(verification.evidence_ids),
            "catalyst_at": verification.catalyst_at,
            "as_of": verification.as_of,
        },
    }
