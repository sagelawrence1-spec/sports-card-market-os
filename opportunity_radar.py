"""Product-facing live Radar intake for sourced opportunity observations.

The Radar may surface narrative/catalyst signals before authoritative market pricing
is available, but it must not turn an unpriced observation into a capital action.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlparse

from opportunity_engine import CardExpression, OpportunityEngine, Signal, SignalKind, Thesis


@dataclass(frozen=True)
class RadarCandidate:
    thesis: Thesis
    decision: str
    market_price_verified: bool
    blocking_reason: str | None
    source_urls: tuple[str, ...]


def _source_urls(payload: Mapping[str, Any]) -> tuple[str, ...]:
    values = tuple(str(value).strip() for value in payload.get("source_urls", ()) if str(value).strip())
    if not values:
        raise ValueError("live Radar observations require at least one source URL")
    for value in values:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"invalid source URL: {value}")
    return values


def evaluate_live_observation(payload: Mapping[str, Any], *, engine: OpportunityEngine | None = None) -> RadarCandidate:
    """Turn a sourced external observation into a lifecycle thesis plus safe decision.

    Lifecycle classification is allowed before pricing is verified. Capital actions are
    not. A candidate without verified repricing is explicitly held at WATCH_FOR_COMPS.
    """
    radar = engine or OpportunityEngine()
    urls = _source_urls(payload)
    market_price_verified = bool(payload.get("market_price_verified", False))
    repricing = payload.get("market_repricing_pct")
    if market_price_verified and repricing is None:
        raise ValueError("verified market pricing requires market_repricing_pct")

    player_id = str(payload["player_id"])
    player = str(payload["player"])
    sport = str(payload["sport"])
    kind = SignalKind(str(payload["signal_kind"]))
    signal = Signal(
        player_id=player_id,
        player=player,
        sport=sport,
        kind=kind,
        description=str(payload["signal_description"]),
        source=urls[0],
        observed_at=str(payload["observed_at"]),
        importance=float(payload.get("importance", 50)),
        novelty=float(payload.get("novelty", 50)),
        market_impact=float(payload.get("market_impact", 50)),
        metadata={"source_urls": urls},
    )
    cards = tuple(
        CardExpression(
            card_id=str(card["card_id"]),
            label=str(card["label"]),
            priority=int(card.get("priority", 1)),
            current_price=card.get("current_price"),
            buy_below=card.get("buy_below"),
            avoid_above=card.get("avoid_above"),
            rationale=str(card.get("rationale", "")),
        )
        for card in payload.get("cards", ())
    )
    thesis = radar.spark(
        player_id=player_id,
        player=player,
        sport=sport,
        signal=signal,
        headline=str(payload["headline"]),
        why_now=str(payload["why_now"]),
        thesis=str(payload["thesis"]),
        falsification=tuple(str(x) for x in payload.get("falsification", ())),
        factors=payload.get("factors", {}),
        cards=cards,
        market_repricing_pct=float(repricing or 0.0),
    )

    if not market_price_verified:
        return RadarCandidate(
            thesis=thesis,
            decision="WATCH_FOR_COMPS",
            market_price_verified=False,
            blocking_reason="authoritative_market_repricing_unverified",
            source_urls=urls,
        )
    return RadarCandidate(
        thesis=thesis,
        decision=thesis.action.value,
        market_price_verified=True,
        blocking_reason=None,
        source_urls=urls,
    )
