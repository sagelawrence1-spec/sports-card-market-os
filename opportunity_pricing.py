"""Leakage-safe repricing verification for live Opportunity Engine candidates.

A catalyst may be surfaced before market pricing is known. This module converts
sufficient authoritative sold evidence into a time-bounded before/after repricing
measurement that Radar can safely use for capital decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Iterable, Mapping, Any


AUTHORITATIVE_SOURCE = "EBAY_PRODUCT_RESEARCH"


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("pricing evidence timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class OpportunityPriceComp:
    evidence_id: str
    card_id: str
    sold_at: str
    landed_price: float
    source_type: str = AUTHORITATIVE_SOURCE


@dataclass(frozen=True)
class RepricingVerification:
    schema: str
    card_id: str
    catalyst_at: str
    as_of: str
    verified: bool
    blocking_reason: str | None
    pre_count: int
    post_count: int
    pre_median: float | None
    post_median: float | None
    repricing_pct: float | None
    evidence_ids: tuple[str, ...]


def verify_repricing(
    *,
    card_id: str,
    catalyst_at: str,
    as_of: str,
    comps: Iterable[OpportunityPriceComp],
    min_pre_comps: int = 3,
    min_post_comps: int = 3,
    pre_window_days: int = 30,
    post_window_days: int = 7,
) -> RepricingVerification:
    """Measure catalyst repricing using only mature evidence known by ``as_of``.

    Pre-catalyst comps are drawn from [catalyst-pre_window, catalyst). Post-catalyst
    comps are drawn from [catalyst, min(as_of, catalyst+post_window)]. Only explicit
    eBay Product Research evidence for the requested card is eligible. Duplicate
    evidence IDs fail closed rather than silently double-weighting the result.
    """
    if not str(card_id).strip():
        raise ValueError("card_id is required")
    if min_pre_comps < 1 or min_post_comps < 1:
        raise ValueError("minimum comp counts must be positive")
    if pre_window_days < 1 or post_window_days < 1:
        raise ValueError("pricing windows must be positive")

    catalyst = _parse_time(catalyst_at)
    cutoff = _parse_time(as_of)
    if cutoff < catalyst:
        raise ValueError("as_of cannot precede catalyst_at")

    pre_start = catalyst - timedelta(days=pre_window_days)
    post_end = min(cutoff, catalyst + timedelta(days=post_window_days))
    pre: list[OpportunityPriceComp] = []
    post: list[OpportunityPriceComp] = []
    seen: set[str] = set()

    for comp in comps:
        evidence_id = str(comp.evidence_id).strip()
        if not evidence_id:
            raise ValueError("pricing evidence requires stable evidence_id")
        if evidence_id in seen:
            raise ValueError(f"duplicate pricing evidence_id: {evidence_id}")
        seen.add(evidence_id)
        if comp.card_id != card_id or comp.source_type != AUTHORITATIVE_SOURCE:
            continue
        price = float(comp.landed_price)
        if price <= 0:
            raise ValueError("landed_price must be positive")
        sold_at = _parse_time(comp.sold_at)
        if sold_at > cutoff:
            continue
        if pre_start <= sold_at < catalyst:
            pre.append(comp)
        elif catalyst <= sold_at <= post_end:
            post.append(comp)

    ids = tuple(sorted(comp.evidence_id for comp in (*pre, *post)))
    if len(pre) < min_pre_comps:
        return RepricingVerification(
            "opportunity-repricing.v1", card_id, catalyst.isoformat(), cutoff.isoformat(),
            False, "insufficient_pre_catalyst_comps", len(pre), len(post), None, None, None, ids,
        )
    if len(post) < min_post_comps:
        return RepricingVerification(
            "opportunity-repricing.v1", card_id, catalyst.isoformat(), cutoff.isoformat(),
            False, "insufficient_post_catalyst_comps", len(pre), len(post), None, None, None, ids,
        )

    pre_median = float(median(float(comp.landed_price) for comp in pre))
    post_median = float(median(float(comp.landed_price) for comp in post))
    repricing = round(((post_median / pre_median) - 1.0) * 100.0, 2)
    return RepricingVerification(
        "opportunity-repricing.v1", card_id, catalyst.isoformat(), cutoff.isoformat(),
        True, None, len(pre), len(post), round(pre_median, 2), round(post_median, 2), repricing, ids,
    )


def apply_verified_repricing(
    payload: Mapping[str, Any], verification: RepricingVerification
) -> dict[str, Any]:
    """Return a Radar payload upgraded only by a successful repricing proof."""
    out = dict(payload)
    if not verification.verified:
        out["market_price_verified"] = False
        out.pop("market_repricing_pct", None)
        return out
    card_ids = {str(card.get("card_id")) for card in payload.get("cards", ())}
    if verification.card_id not in card_ids:
        raise ValueError("repricing verification card must be an expression on the thesis")
    out["market_price_verified"] = True
    out["market_repricing_pct"] = verification.repricing_pct
    out["pricing_verification"] = {
        "schema": verification.schema,
        "card_id": verification.card_id,
        "as_of": verification.as_of,
        "pre_count": verification.pre_count,
        "post_count": verification.post_count,
        "pre_median": verification.pre_median,
        "post_median": verification.post_median,
        "evidence_ids": verification.evidence_ids,
    }
    return out
