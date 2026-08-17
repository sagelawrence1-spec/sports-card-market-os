"""Focused Opportunity Engine MVP: Radar -> Thesis -> Clock -> Cards -> Ledger.

This module is intentionally product-facing.  It turns weak/strong market signals
into timestamped opportunity theses without pretending that narrative evidence is
more authoritative than it is.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Mapping
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 1)


class ThesisType(str, Enum):
    EDGE = "EDGE"
    CATALYST = "CATALYST"
    QUANT = "QUANT"


class OpportunityStage(str, Enum):
    PRE_CATALYST = "PRE_CATALYST"
    ENTRY = "ENTRY"
    ACCELERATION = "ACCELERATION"
    CONSENSUS = "CONSENSUS"
    BROKEN = "BROKEN"


class OpportunityAction(str, Enum):
    WATCH = "WATCH"
    START_POSITION = "START_POSITION"
    ADD = "ADD"
    HOLD = "HOLD"
    DO_NOT_CHASE = "DO_NOT_CHASE"
    EXIT = "EXIT"


class SignalKind(str, Enum):
    USER_SPARK = "USER_SPARK"
    SIGNING = "SIGNING"
    TRADE = "TRADE"
    CALL_UP = "CALL_UP"
    PLAYING_TIME = "PLAYING_TIME"
    PERFORMANCE = "PERFORMANCE"
    MILESTONE = "MILESTONE"
    RETIREMENT = "RETIREMENT"
    HOF = "HOF"
    MEDIA = "MEDIA"
    SEARCH = "SEARCH"
    SALES_VELOCITY = "SALES_VELOCITY"
    PRICE = "PRICE"


@dataclass(frozen=True)
class Signal:
    player_id: str
    player: str
    sport: str
    kind: SignalKind
    description: str
    source: str
    observed_at: str = field(default_factory=_now)
    importance: float = 50.0
    novelty: float = 50.0
    market_impact: float = 50.0
    signal_id: str = field(default_factory=lambda: str(uuid4()))
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CardExpression:
    card_id: str
    label: str
    priority: int = 1
    current_price: float | None = None
    buy_below: float | None = None
    avoid_above: float | None = None
    rationale: str = ""


@dataclass(frozen=True)
class Thesis:
    thesis_id: str
    player_id: str
    player: str
    sport: str
    thesis_type: ThesisType
    stage: OpportunityStage
    action: OpportunityAction
    headline: str
    why_now: str
    thesis: str
    falsification: tuple[str, ...]
    evidence_confidence: float
    edge_conviction: float
    asymmetry: float
    signals: tuple[Signal, ...] = ()
    cards: tuple[CardExpression, ...] = ()
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)


@dataclass(frozen=True)
class LedgerEntry:
    thesis_id: str
    observed_at: str
    stage: OpportunityStage
    action: OpportunityAction
    edge_conviction: float
    evidence_confidence: float
    reason: str


_CATALYST = {SignalKind.SIGNING, SignalKind.TRADE, SignalKind.CALL_UP, SignalKind.MILESTONE, SignalKind.RETIREMENT, SignalKind.HOF}
_QUANT = {SignalKind.SALES_VELOCITY, SignalKind.PRICE}
_ACCELERATION = {SignalKind.PERFORMANCE, SignalKind.MEDIA, SignalKind.SEARCH, SignalKind.SALES_VELOCITY, SignalKind.PRICE}
_STAGE_ORDER = {OpportunityStage.PRE_CATALYST: 0, OpportunityStage.ENTRY: 1, OpportunityStage.ACCELERATION: 2, OpportunityStage.CONSENSUS: 3, OpportunityStage.BROKEN: 99}


def classify_type(kind: SignalKind) -> ThesisType:
    if kind in _CATALYST:
        return ThesisType.CATALYST
    if kind in _QUANT:
        return ThesisType.QUANT
    return ThesisType.EDGE


def candidate_stage(kind: SignalKind) -> OpportunityStage:
    if kind in _CATALYST or kind == SignalKind.PLAYING_TIME:
        return OpportunityStage.ENTRY
    if kind in _ACCELERATION:
        return OpportunityStage.ACCELERATION
    return OpportunityStage.PRE_CATALYST


def score_factors(factors: Mapping[str, float]) -> tuple[float, float, float]:
    """Return evidence confidence, edge conviction and asymmetry independently."""
    situation = _clamp(factors.get("situation_change", 50))
    narrative = _clamp(factors.get("narrative_potential", 50))
    collectibility = _clamp(factors.get("collectibility", 50))
    lag = _clamp(factors.get("hobby_lag", 50))
    attention = _clamp(factors.get("attention_velocity", 50))
    maturity = _clamp(factors.get("evidence_maturity", 50))
    asymmetry = _clamp(factors.get("upside_asymmetry", 50))
    evidence = _clamp(.55*maturity + .15*situation + .15*attention + .15*collectibility)
    edge = _clamp(.23*asymmetry + .22*lag + .17*narrative + .14*collectibility + .14*situation + .10*attention)
    return evidence, edge, asymmetry


def choose_action(stage: OpportunityStage, edge: float, asymmetry: float, repricing_pct: float = 0.0) -> OpportunityAction:
    if stage == OpportunityStage.BROKEN:
        return OpportunityAction.EXIT
    if stage == OpportunityStage.CONSENSUS or repricing_pct >= 35:
        return OpportunityAction.DO_NOT_CHASE
    if stage == OpportunityStage.PRE_CATALYST:
        return OpportunityAction.START_POSITION if edge >= 78 and asymmetry >= 75 else OpportunityAction.WATCH
    if stage == OpportunityStage.ENTRY:
        return OpportunityAction.START_POSITION if edge >= 65 and asymmetry >= 65 else OpportunityAction.WATCH
    if stage == OpportunityStage.ACCELERATION:
        if edge >= 72 and asymmetry >= 65:
            return OpportunityAction.ADD
        return OpportunityAction.START_POSITION if edge >= 62 and repricing_pct < 20 else OpportunityAction.WATCH
    return OpportunityAction.HOLD


class OpportunityEngine:
    """In-memory MVP orchestrator. Persistence is supplied by the existing journal layer later."""
    def __init__(self) -> None:
        self._theses: dict[str, Thesis] = {}
        self._ledger: list[LedgerEntry] = []

    def spark(self, *, player_id: str, player: str, sport: str, signal: Signal, headline: str, why_now: str, thesis: str, falsification: Iterable[str], factors: Mapping[str, float], cards: Iterable[CardExpression] = (), market_repricing_pct: float = 0.0) -> Thesis:
        if signal.player_id != player_id:
            raise ValueError("Signal player identity must match thesis player identity.")
        evidence, edge, asymmetry = score_factors(factors)
        stage = candidate_stage(signal.kind)
        action = choose_action(stage, edge, asymmetry, market_repricing_pct)
        out = Thesis(str(uuid4()), player_id, player, sport, classify_type(signal.kind), stage, action, headline, why_now, thesis, tuple(falsification), evidence, edge, asymmetry, (signal,), tuple(cards))
        self._theses[out.thesis_id] = out
        self._record(out, "spark")
        return out

    def apply_signal(self, thesis_id: str, signal: Signal, *, factors: Mapping[str, float], market_repricing_pct: float = 0.0) -> Thesis:
        current = self._theses[thesis_id]
        if signal.player_id != current.player_id:
            raise ValueError("Signal player identity must match existing thesis.")
        evidence, edge, asymmetry = score_factors(factors)
        proposed = candidate_stage(signal.kind)
        stage = proposed if _STAGE_ORDER[proposed] > _STAGE_ORDER[current.stage] else current.stage
        action = choose_action(stage, edge, asymmetry, market_repricing_pct)
        updated = replace(current, stage=stage, action=action, evidence_confidence=evidence, edge_conviction=edge, asymmetry=asymmetry, signals=current.signals + (signal,), updated_at=_now())
        self._theses[thesis_id] = updated
        self._record(updated, signal.description)
        return updated

    def mark_consensus(self, thesis_id: str, reason: str) -> Thesis:
        return self._force_stage(thesis_id, OpportunityStage.CONSENSUS, reason)

    def break_thesis(self, thesis_id: str, reason: str) -> Thesis:
        return self._force_stage(thesis_id, OpportunityStage.BROKEN, reason)

    def _force_stage(self, thesis_id: str, stage: OpportunityStage, reason: str) -> Thesis:
        current = self._theses[thesis_id]
        action = choose_action(stage, current.edge_conviction, current.asymmetry)
        updated = replace(current, stage=stage, action=action, updated_at=_now())
        self._theses[thesis_id] = updated
        self._record(updated, reason)
        return updated

    def _record(self, thesis: Thesis, reason: str) -> None:
        self._ledger.append(LedgerEntry(thesis.thesis_id, thesis.updated_at, thesis.stage, thesis.action, thesis.edge_conviction, thesis.evidence_confidence, reason))

    def ledger(self, thesis_id: str) -> tuple[LedgerEntry, ...]:
        return tuple(row for row in self._ledger if row.thesis_id == thesis_id)

    def radar(self) -> tuple[Thesis, ...]:
        priority = {OpportunityStage.ENTRY: 5, OpportunityStage.ACCELERATION: 4, OpportunityStage.PRE_CATALYST: 3, OpportunityStage.CONSENSUS: 2, OpportunityStage.BROKEN: 0}
        return tuple(sorted(self._theses.values(), key=lambda t: (priority[t.stage], t.edge_conviction, t.asymmetry), reverse=True))
