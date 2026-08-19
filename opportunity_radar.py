"""Product-facing live Radar intake for sourced opportunity observations.

The Radar may surface narrative/catalyst signals before authoritative market pricing
is available, but it must not turn an unpriced observation into a capital action.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

from opportunity_engine import CardExpression, OpportunityEngine, Signal, SignalKind, Thesis


@dataclass(frozen=True)
class RadarCandidate:
    thesis: Thesis
    decision: str
    market_price_verified: bool
    blocking_reason: str | None
    source_urls: tuple[str, ...]
    source_quality: str = "SINGLE_SOURCE"
    source_host_count: int = 1


@dataclass(frozen=True)
class RadarBatchFailure:
    index: int
    player_id: str | None
    reason: str


@dataclass(frozen=True)
class RadarBatchReport:
    schema: str
    candidates: tuple[RadarCandidate, ...]
    failures: tuple[RadarBatchFailure, ...]
    input_count: int
    duplicate_count: int

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def actionable_count(self) -> int:
        return sum(candidate.decision not in {"WATCH", "WATCH_FOR_COMPS", "DO_NOT_CHASE"} for candidate in self.candidates)


# Event-status catalysts are especially vulnerable to rumor contamination. A single
# unconfirmed blog/social source may surface in Radar, but it should not unlock
# capital merely because sold comps are already available.
_CONFIRMATION_REQUIRED = {
    SignalKind.CALL_UP_WATCH,
    SignalKind.SIGNING,
    SignalKind.TRADE,
    SignalKind.CALL_UP,
    SignalKind.RETIREMENT,
    SignalKind.HOF,
}
_OFFICIAL_CATALYST_DOMAINS = {
    "mlb.com",
    "milb.com",
    "nfl.com",
    "nba.com",
    "wnba.com",
    "nhl.com",
}
# These hosts may be valuable provenance for card/checklist identity, but they do not
# independently corroborate that the real-world catalyst itself occurred. Counting a
# checklist source as a second catalyst source would create false corroboration.
_SUPPORT_ONLY_SOURCE_DOMAINS = {
    "beckett.com",
}
_SOURCE_QUALITY_RANK = {
    "OFFICIAL": 2,
    "CORROBORATED": 1,
    "SINGLE_SOURCE": 0,
}


def _source_urls(payload: Mapping[str, Any]) -> tuple[str, ...]:
    values = tuple(str(value).strip() for value in payload.get("source_urls", ()) if str(value).strip())
    if not values:
        raise ValueError("live Radar observations require at least one source URL")
    for value in values:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"invalid source URL: {value}")
    return values


def _source_host(value: str) -> str:
    host = (urlparse(value).hostname or "").casefold().strip(".")
    return host[4:] if host.startswith("www.") else host


def _is_official_catalyst_host(host: str) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in _OFFICIAL_CATALYST_DOMAINS)


def _is_support_only_source_host(host: str) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in _SUPPORT_ONLY_SOURCE_DOMAINS)


def _source_quality(urls: tuple[str, ...]) -> tuple[str, int]:
    """Return catalyst provenance quality without letting card-reference sources corroborate events."""
    hosts = {_source_host(value) for value in urls}
    hosts.discard("")
    catalyst_hosts = {host for host in hosts if not _is_support_only_source_host(host)}
    if any(_is_official_catalyst_host(host) for host in catalyst_hosts):
        return "OFFICIAL", len(catalyst_hosts)
    if len(catalyst_hosts) >= 2:
        return "CORROBORATED", len(catalyst_hosts)
    return "SINGLE_SOURCE", len(catalyst_hosts)


def _catalyst_source_confirmed(kind: SignalKind, urls: tuple[str, ...]) -> bool:
    """Require official confirmation or independent corroboration for event catalysts.

    Performance/attention signals intentionally remain eligible from one credible
    source because Radar is supposed to surface weak signals early. Event-status
    claims such as a trade or call-up are different: one unconfirmed source can move
    the hobby while still being wrong, so pricing evidence alone cannot validate the
    underlying event.
    """
    if kind not in _CONFIRMATION_REQUIRED:
        return True
    quality, _ = _source_quality(urls)
    return quality in {"OFFICIAL", "CORROBORATED"}


def _observation_key(payload: Mapping[str, Any]) -> tuple[str, str, str, str]:
    """Return stable event identity so one catalyst cannot inflate Radar breadth."""
    return (
        str(payload.get("player_id", "")).strip(),
        str(payload.get("signal_kind", "")).strip(),
        str(payload.get("observed_at", "")).strip(),
        str(payload.get("headline", "")).strip().casefold(),
    )


def evaluate_live_observation(payload: Mapping[str, Any], *, engine: OpportunityEngine | None = None) -> RadarCandidate:
    """Turn a sourced external observation into a lifecycle thesis plus safe decision.

    Lifecycle classification is allowed before pricing is verified. Capital actions are
    not. A candidate without verified repricing is explicitly held at WATCH_FOR_COMPS.
    Event-status catalysts also require credible source confirmation before pricing can
    unlock capital.
    """
    radar = engine or OpportunityEngine()
    urls = _source_urls(payload)
    source_quality, source_host_count = _source_quality(urls)
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
        metadata={
            "source_urls": urls,
            "source_quality": source_quality,
            "source_host_count": source_host_count,
        },
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
            source_quality=source_quality,
            source_host_count=source_host_count,
        )
    if not _catalyst_source_confirmed(kind, urls):
        return RadarCandidate(
            thesis=thesis,
            decision="WATCH",
            market_price_verified=True,
            blocking_reason="catalyst_source_unconfirmed",
            source_urls=urls,
            source_quality=source_quality,
            source_host_count=source_host_count,
        )
    return RadarCandidate(
        thesis=thesis,
        decision=thesis.action.value,
        market_price_verified=True,
        blocking_reason=None,
        source_urls=urls,
        source_quality=source_quality,
        source_host_count=source_host_count,
    )


def scan_live_observations(payloads: Iterable[Mapping[str, Any]]) -> RadarBatchReport:
    """Evaluate a live Radar scan without letting one malformed event erase the scan.

    Duplicate event identities are collapsed before evaluation. Valid candidates are
    ranked by edge conviction, then evidence confidence, then source provenance as a
    deterministic tie-break. Source quality never changes capital thresholds.
    Failures remain explicit so breadth metrics cannot silently ignore bad intake rows.
    """
    rows = list(payloads)
    seen: set[tuple[str, str, str, str]] = set()
    candidates: list[RadarCandidate] = []
    failures: list[RadarBatchFailure] = []
    duplicate_count = 0

    for index, payload in enumerate(rows):
        key = _observation_key(payload)
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        try:
            candidates.append(evaluate_live_observation(payload))
        except (KeyError, TypeError, ValueError) as exc:
            player_id = str(payload.get("player_id", "")).strip() or None
            failures.append(RadarBatchFailure(index=index, player_id=player_id, reason=str(exc)))

    candidates.sort(
        key=lambda candidate: (
            -candidate.thesis.edge_conviction,
            -candidate.thesis.evidence_confidence,
            -_SOURCE_QUALITY_RANK[candidate.source_quality],
            candidate.thesis.player_id,
            candidate.thesis.headline.casefold(),
        )
    )
    return RadarBatchReport(
        schema="opportunity-radar-batch.v1",
        candidates=tuple(candidates),
        failures=tuple(failures),
        input_count=len(rows),
        duplicate_count=duplicate_count,
    )
