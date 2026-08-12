"""Opportunity Engine MVP for Sports Card Market OS.

The engine captures pre-consensus player hypotheses separately from the existing
card-level quant engine. It intentionally keeps evidence confidence distinct from
edge conviction so weak-signal ideas can be journaled without pretending they are
fully proven.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 1)


class OpportunityType(str, Enum):
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
    TRIM = "TRIM"
    EXIT = "EXIT"


class SignalType(str, Enum):
    SIGNING = "SIGNING"
    TRADE = "TRADE"
    CALL_UP = "CALL_UP"
    DEBUT = "DEBUT"
    LINEUP_CHANGE = "LINEUP_CHANGE"
    PLAYING_TIME_CHANGE = "PLAYING_TIME_CHANGE"
    FIRST_MAJOR_EVENT = "FIRST_MAJOR_EVENT"
    PERFORMANCE_SPIKE = "PERFORMANCE_SPIKE"
    MILESTONE_APPROACH = "MILESTONE_APPROACH"
    AWARD_TRAJECTORY = "AWARD_TRAJECTORY"
    RETIREMENT_RISK = "RETIREMENT_RISK"
    HOF_CATALYST = "HOF_CATALYST"
    MEDIA_ATTENTION = "MEDIA_ATTENTION"
    SEARCH_ATTENTION = "SEARCH_ATTENTION"
    CARD_VOLUME_SPIKE = "CARD_VOLUME_SPIKE"
    CARD_PRICE_MOVE = "CARD_PRICE_MOVE"
    USER_SPARK = "USER_SPARK"


class TargetPriority(str, Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    SPECULATIVE = "SPECULATIVE"


@dataclass(frozen=True)
class OpportunityScores:
    evidence_confidence: float
    edge_conviction: float
    asymmetry_rating: float

    def to_dict(self) -> dict[str, float]:
        return {
            "evidence_confidence": self.evidence_confidence,
            "edge_conviction": self.edge_conviction,
            "asymmetry_rating": self.asymmetry_rating,
        }


@dataclass(frozen=True)
class PlayerSignal:
    player_id: str
    player: str
    sport: str
    signal_type: SignalType
    source: str
    description: str
    importance: float = 50.0
    novelty: float = 50.0
    potential_market_impact: float = 50.0
    timestamp: str = field(default_factory=utc_now)
    signal_id: str = field(default_factory=lambda: str(uuid4()))
    linked_thesis_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "player_id": self.player_id,
            "player": self.player,
            "sport": self.sport,
            "signal_type": self.signal_type.value,
            "source": self.source,
            "description": self.description,
            "importance": _clamp(self.importance),
            "novelty": _clamp(self.novelty),
            "potential_market_impact": _clamp(self.potential_market_impact),
            "timestamp": self.timestamp,
            "linked_thesis_id": self.linked_thesis_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CardTarget:
    card_id: str
    year: str
    set_name: str
    card_number: str = ""
    parallel: str = ""
    grade: str = ""
    current_price: float | None = None
    target_entry_price: float | None = None
    population: int | None = None
    recent_sales_volume: int | None = None
    liquidity: float | None = None
    why_this_card: str = ""
    priority: TargetPriority = TargetPriority.PRIMARY
    buy_below: float | None = None
    avoid_above: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.__dict__)
        data["priority"] = self.priority.value
        return data


@dataclass(frozen=True)
class OpportunityThesis:
    thesis_id: str
    player_id: str
    player: str
    sport: str
    opportunity_type: OpportunityType
    stage: OpportunityStage
    headline: str
    thesis: str
    why_now: str
    bull_case: str
    bear_case: str
    kill_conditions: tuple[str, ...]
    evidence_confidence: float
    edge_conviction: float
    asymmetry_rating: float
    recommended_action: OpportunityAction
    max_position_size: float | None = None
    card_targets: tuple[CardTarget, ...] = ()
    next_confirmation_events: tuple[str, ...] = ()
    created_at: str = field(default_factory=utc_now)
    last_updated_at: str = field(default_factory=utc_now)
    initial_price_snapshot: dict[str, float] = field(default_factory=dict)
    current_price_snapshot: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "thesis_id": self.thesis_id,
            "player_id": self.player_id,
            "player": self.player,
            "sport": self.sport,
            "opportunity_type": self.opportunity_type.value,
            "stage": self.stage.value,
            "headline": self.headline,
            "thesis": self.thesis,
            "why_now": self.why_now,
            "bull_case": self.bull_case,
            "bear_case": self.bear_case,
            "kill_conditions": list(self.kill_conditions),
            "evidence_confidence": _clamp(self.evidence_confidence),
            "edge_conviction": _clamp(self.edge_conviction),
            "asymmetry_rating": _clamp(self.asymmetry_rating),
            "recommended_action": self.recommended_action.value,
            "max_position_size": self.max_position_size,
            "card_targets": [target.to_dict() for target in self.card_targets],
            "next_confirmation_events": list(self.next_confirmation_events),
            "created_at": self.created_at,
            "last_updated_at": self.last_updated_at,
            "initial_price_snapshot": dict(self.initial_price_snapshot),
            "current_price_snapshot": dict(self.current_price_snapshot),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "OpportunityThesis":
        targets = []
        for item in raw.get("card_targets", []):
            target = dict(item)
            if "set_name" not in target:
                target["set_name"] = target.get("set", "")
            target.pop("set", None)
            target["priority"] = TargetPriority(target.get("priority", "PRIMARY"))
            targets.append(CardTarget(**target))
        targets = tuple(targets)
        return cls(
            thesis_id=str(raw["thesis_id"]),
            player_id=str(raw["player_id"]),
            player=str(raw["player"]),
            sport=str(raw["sport"]),
            opportunity_type=OpportunityType(raw["opportunity_type"]),
            stage=OpportunityStage(raw["stage"]),
            headline=str(raw.get("headline", "")),
            thesis=str(raw.get("thesis", "")),
            why_now=str(raw.get("why_now", "")),
            bull_case=str(raw.get("bull_case", "")),
            bear_case=str(raw.get("bear_case", "")),
            kill_conditions=tuple(raw.get("kill_conditions", [])),
            evidence_confidence=float(raw.get("evidence_confidence", 0)),
            edge_conviction=float(raw.get("edge_conviction", 0)),
            asymmetry_rating=float(raw.get("asymmetry_rating", 0)),
            recommended_action=OpportunityAction(raw.get("recommended_action", "WATCH")),
            max_position_size=raw.get("max_position_size"),
            card_targets=targets,
            next_confirmation_events=tuple(raw.get("next_confirmation_events", [])),
            created_at=str(raw.get("created_at", utc_now())),
            last_updated_at=str(raw.get("last_updated_at", utc_now())),
            initial_price_snapshot=dict(raw.get("initial_price_snapshot", {})),
            current_price_snapshot=dict(raw.get("current_price_snapshot", {})),
            metadata=dict(raw.get("metadata", {})),
        )


@dataclass(frozen=True)
class ThesisLedgerEntry:
    thesis_id: str
    timestamp: str
    stage: OpportunityStage
    recommendation: OpportunityAction
    evidence_confidence: float
    edge_conviction: float
    asymmetry_rating: float
    reason: str
    price_snapshot: dict[str, float] = field(default_factory=dict)
    thesis_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "thesis_id": self.thesis_id,
            "timestamp": self.timestamp,
            "stage": self.stage.value,
            "recommendation": self.recommendation.value,
            "evidence_confidence": self.evidence_confidence,
            "edge_conviction": self.edge_conviction,
            "asymmetry_rating": self.asymmetry_rating,
            "reason": self.reason,
            "price_snapshot": dict(self.price_snapshot),
            "thesis_snapshot": dict(self.thesis_snapshot),
        }


FACTOR_KEYS = (
    "situation_change",
    "narrative_potential",
    "collectibility",
    "hobby_lag",
    "attention_velocity",
    "evidence_maturity",
    "upside_asymmetry",
)


def score_opportunity_factors(factors: Mapping[str, float]) -> OpportunityScores:
    """Turn observable proxies into separate evidence and edge scores.

    Evidence intentionally leans heavily on maturity. Edge leans on lag, asymmetry,
    narrative, and collectibility so a thesis can be interesting before it is proven.
    """
    f = {key: _clamp(factors.get(key, 50.0)) for key in FACTOR_KEYS}
    evidence = (
        0.55 * f["evidence_maturity"]
        + 0.15 * f["situation_change"]
        + 0.15 * f["attention_velocity"]
        + 0.15 * f["collectibility"]
    )
    edge = (
        0.23 * f["upside_asymmetry"]
        + 0.22 * f["hobby_lag"]
        + 0.17 * f["narrative_potential"]
        + 0.14 * f["collectibility"]
        + 0.14 * f["situation_change"]
        + 0.10 * f["attention_velocity"]
    )
    return OpportunityScores(_clamp(evidence), _clamp(edge), f["upside_asymmetry"])


_STAGE_ORDER = {
    OpportunityStage.PRE_CATALYST: 0,
    OpportunityStage.ENTRY: 1,
    OpportunityStage.ACCELERATION: 2,
    OpportunityStage.CONSENSUS: 3,
    OpportunityStage.BROKEN: 99,
}


def infer_opportunity_type(signal_type: SignalType) -> OpportunityType:
    if signal_type in {
        SignalType.SIGNING,
        SignalType.TRADE,
        SignalType.CALL_UP,
        SignalType.DEBUT,
        SignalType.MILESTONE_APPROACH,
        SignalType.RETIREMENT_RISK,
        SignalType.HOF_CATALYST,
    }:
        return OpportunityType.CATALYST
    if signal_type in {SignalType.CARD_VOLUME_SPIKE, SignalType.CARD_PRICE_MOVE}:
        return OpportunityType.QUANT
    return OpportunityType.EDGE


def infer_stage(signal_type: SignalType) -> OpportunityStage:
    if signal_type in {
        SignalType.SIGNING,
        SignalType.TRADE,
        SignalType.CALL_UP,
        SignalType.DEBUT,
        SignalType.LINEUP_CHANGE,
        SignalType.PLAYING_TIME_CHANGE,
        SignalType.MILESTONE_APPROACH,
        SignalType.RETIREMENT_RISK,
        SignalType.HOF_CATALYST,
    }:
        return OpportunityStage.ENTRY
    if signal_type in {
        SignalType.FIRST_MAJOR_EVENT,
        SignalType.PERFORMANCE_SPIKE,
        SignalType.AWARD_TRAJECTORY,
        SignalType.MEDIA_ATTENTION,
        SignalType.SEARCH_ATTENTION,
        SignalType.CARD_VOLUME_SPIKE,
        SignalType.CARD_PRICE_MOVE,
    }:
        return OpportunityStage.ACCELERATION
    return OpportunityStage.PRE_CATALYST


def advance_stage(current: OpportunityStage, candidate: OpportunityStage) -> OpportunityStage:
    if current == OpportunityStage.BROKEN:
        return current
    if candidate == OpportunityStage.BROKEN:
        return candidate
    return candidate if _STAGE_ORDER[candidate] > _STAGE_ORDER[current] else current


def recommend_action(
    stage: OpportunityStage,
    scores: OpportunityScores,
    *,
    market_repricing_pct: float = 0.0,
) -> OpportunityAction:
    if stage == OpportunityStage.BROKEN:
        return OpportunityAction.EXIT
    if stage == OpportunityStage.CONSENSUS:
        return OpportunityAction.DO_NOT_CHASE
    if stage == OpportunityStage.PRE_CATALYST:
        if scores.edge_conviction >= 78 and scores.asymmetry_rating >= 75:
            return OpportunityAction.START_POSITION
        return OpportunityAction.WATCH
    if stage == OpportunityStage.ENTRY:
        if market_repricing_pct >= 35:
            return OpportunityAction.DO_NOT_CHASE
        if scores.edge_conviction >= 65 and scores.asymmetry_rating >= 65:
            return OpportunityAction.START_POSITION
        return OpportunityAction.WATCH
    if market_repricing_pct >= 35:
        return OpportunityAction.DO_NOT_CHASE
    if scores.edge_conviction >= 72 and scores.asymmetry_rating >= 65:
        return OpportunityAction.ADD
    if scores.edge_conviction >= 62 and market_repricing_pct < 20:
        return OpportunityAction.START_POSITION
    return OpportunityAction.WATCH


SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunity_theses(
  thesis_id TEXT PRIMARY KEY,
  player_id TEXT NOT NULL,
  player TEXT NOT NULL,
  sport TEXT NOT NULL,
  opportunity_type TEXT NOT NULL,
  stage TEXT NOT NULL,
  action TEXT NOT NULL,
  evidence_confidence REAL NOT NULL,
  edge_conviction REAL NOT NULL,
  asymmetry_rating REAL NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_opportunity_player ON opportunity_theses(player_id);
CREATE INDEX IF NOT EXISTS idx_opportunity_stage ON opportunity_theses(stage);

CREATE TABLE IF NOT EXISTS opportunity_signals(
  signal_id TEXT PRIMARY KEY,
  thesis_id TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  signal_type TEXT NOT NULL,
  source TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_opportunity_signal_thesis ON opportunity_signals(thesis_id, timestamp);

CREATE TABLE IF NOT EXISTS opportunity_ledger(
  ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
  thesis_id TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  stage TEXT NOT NULL,
  action TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_opportunity_ledger_thesis ON opportunity_ledger(thesis_id, ledger_id);
"""


class OpportunityStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def save_thesis(self, thesis: OpportunityThesis) -> None:
        raw = thesis.to_dict()
        self.conn.execute(
            """
            INSERT INTO opportunity_theses(
              thesis_id,player_id,player,sport,opportunity_type,stage,action,
              evidence_confidence,edge_conviction,asymmetry_rating,created_at,updated_at,payload_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(thesis_id) DO UPDATE SET
              player_id=excluded.player_id,
              player=excluded.player,
              sport=excluded.sport,
              opportunity_type=excluded.opportunity_type,
              stage=excluded.stage,
              action=excluded.action,
              evidence_confidence=excluded.evidence_confidence,
              edge_conviction=excluded.edge_conviction,
              asymmetry_rating=excluded.asymmetry_rating,
              updated_at=excluded.updated_at,
              payload_json=excluded.payload_json
            """,
            (
                thesis.thesis_id,
                thesis.player_id,
                thesis.player,
                thesis.sport,
                thesis.opportunity_type.value,
                thesis.stage.value,
                thesis.recommended_action.value,
                thesis.evidence_confidence,
                thesis.edge_conviction,
                thesis.asymmetry_rating,
                thesis.created_at,
                thesis.last_updated_at,
                json.dumps(raw, sort_keys=True),
            ),
        )
        self.conn.commit()

    def get_thesis(self, thesis_id: str) -> OpportunityThesis | None:
        row = self.conn.execute(
            "SELECT payload_json FROM opportunity_theses WHERE thesis_id=?", (thesis_id,)
        ).fetchone()
        return OpportunityThesis.from_dict(json.loads(row[0])) if row else None

    def find_active_player(self, player_id: str) -> OpportunityThesis | None:
        row = self.conn.execute(
            """SELECT payload_json FROM opportunity_theses
               WHERE player_id=? AND stage != 'BROKEN'
               ORDER BY updated_at DESC LIMIT 1""",
            (player_id,),
        ).fetchone()
        return OpportunityThesis.from_dict(json.loads(row[0])) if row else None

    def list_theses(self, *, include_broken: bool = False) -> list[OpportunityThesis]:
        where = "" if include_broken else "WHERE stage != 'BROKEN'"
        rows = self.conn.execute(
            f"SELECT payload_json FROM opportunity_theses {where} ORDER BY updated_at DESC"
        ).fetchall()
        return [OpportunityThesis.from_dict(json.loads(row[0])) for row in rows]

    def append_signal(self, thesis_id: str, signal: PlayerSignal) -> None:
        raw = signal.to_dict()
        self.conn.execute(
            "INSERT OR IGNORE INTO opportunity_signals VALUES(?,?,?,?,?,?)",
            (
                signal.signal_id,
                thesis_id,
                signal.timestamp,
                signal.signal_type.value,
                signal.source,
                json.dumps(raw, sort_keys=True),
            ),
        )
        self.conn.commit()

    def append_ledger(self, entry: ThesisLedgerEntry) -> None:
        self.conn.execute(
            "INSERT INTO opportunity_ledger(thesis_id,timestamp,stage,action,payload_json) VALUES(?,?,?,?,?)",
            (
                entry.thesis_id,
                entry.timestamp,
                entry.stage.value,
                entry.recommendation.value,
                json.dumps(entry.to_dict(), sort_keys=True),
            ),
        )
        self.conn.commit()

    def ledger(self, thesis_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT payload_json FROM opportunity_ledger WHERE thesis_id=? ORDER BY ledger_id",
            (thesis_id,),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def signals(self, thesis_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT payload_json FROM opportunity_signals WHERE thesis_id=? ORDER BY timestamp",
            (thesis_id,),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]


DEFAULT_SPARK_FACTORS = {
    "situation_change": 55,
    "narrative_potential": 55,
    "collectibility": 55,
    "hobby_lag": 65,
    "attention_velocity": 45,
    "evidence_maturity": 20,
    "upside_asymmetry": 65,
}


class OpportunityEngine:
    def __init__(self, store: OpportunityStore):
        self.store = store

    def _journal(self, thesis: OpportunityThesis, reason: str) -> None:
        self.store.append_ledger(
            ThesisLedgerEntry(
                thesis_id=thesis.thesis_id,
                timestamp=thesis.last_updated_at,
                stage=thesis.stage,
                recommendation=thesis.recommended_action,
                evidence_confidence=thesis.evidence_confidence,
                edge_conviction=thesis.edge_conviction,
                asymmetry_rating=thesis.asymmetry_rating,
                reason=reason,
                price_snapshot=dict(thesis.current_price_snapshot),
                thesis_snapshot=thesis.to_dict(),
            )
        )

    def spark(
        self,
        *,
        player: str,
        sport: str,
        observation: str,
        player_id: str | None = None,
        signal_type: SignalType = SignalType.USER_SPARK,
        factors: Mapping[str, float] | None = None,
        opportunity_type: OpportunityType | None = None,
        market_repricing_pct: float = 0.0,
        source: str = "user_spark",
        card_targets: Iterable[CardTarget] = (),
        max_position_size: float | None = None,
    ) -> OpportunityThesis:
        player_id = player_id or player.strip().lower().replace(" ", "-")
        scores = score_opportunity_factors(factors or DEFAULT_SPARK_FACTORS)
        signal = PlayerSignal(
            player_id=player_id,
            player=player,
            sport=sport,
            signal_type=signal_type,
            source=source,
            description=observation,
            importance=scores.edge_conviction,
            novelty=70 if signal_type == SignalType.USER_SPARK else 60,
            potential_market_impact=scores.asymmetry_rating,
        )
        existing = self.store.find_active_player(player_id)
        if existing:
            return self.apply_signal(
                existing.thesis_id,
                signal,
                factors=factors,
                market_repricing_pct=market_repricing_pct,
            )

        stage = infer_stage(signal_type)
        opportunity_type = opportunity_type or infer_opportunity_type(signal_type)
        action = recommend_action(stage, scores, market_repricing_pct=market_repricing_pct)
        now = utc_now()
        thesis_id = str(uuid4())
        linked_signal = replace(signal, linked_thesis_id=thesis_id)
        thesis = OpportunityThesis(
            thesis_id=thesis_id,
            player_id=player_id,
            player=player,
            sport=sport,
            opportunity_type=opportunity_type,
            stage=stage,
            headline=f"{player}: pre-consensus opportunity under review",
            thesis="A potentially investable player-level change is occurring before the card market has fully confirmed or priced it.",
            why_now=observation,
            bull_case="The real-world player narrative strengthens faster than relevant card prices reprice.",
            bear_case="The signal fails to persist, or the hobby reprices before sufficient upside remains.",
            kill_conditions=(
                "real-world thesis materially deteriorates",
                "market reprices beyond the modeled entry window before confirmation",
            ),
            evidence_confidence=scores.evidence_confidence,
            edge_conviction=scores.edge_conviction,
            asymmetry_rating=scores.asymmetry_rating,
            recommended_action=action,
            max_position_size=max_position_size,
            card_targets=tuple(card_targets),
            next_confirmation_events=(
                "new real-world signal",
                "measurable attention acceleration",
                "card-market repricing or liquidity change",
            ),
            created_at=now,
            last_updated_at=now,
            metadata={"market_repricing_pct": market_repricing_pct},
        )
        self.store.save_thesis(thesis)
        self.store.append_signal(thesis_id, linked_signal)
        self._journal(thesis, f"Created from {signal_type.value}: {observation}")
        return thesis

    def apply_signal(
        self,
        thesis_id: str,
        signal: PlayerSignal,
        *,
        factors: Mapping[str, float] | None = None,
        market_repricing_pct: float = 0.0,
    ) -> OpportunityThesis:
        current = self.store.get_thesis(thesis_id)
        if current is None:
            raise KeyError(f"Unknown thesis_id: {thesis_id}")
        if current.stage == OpportunityStage.BROKEN:
            raise ValueError("Broken theses are immutable; create a new thesis for a new setup.")

        scores = score_opportunity_factors(factors or {
            "situation_change": signal.importance,
            "narrative_potential": current.edge_conviction,
            "collectibility": current.edge_conviction,
            "hobby_lag": max(0.0, 100.0 - market_repricing_pct),
            "attention_velocity": signal.potential_market_impact,
            "evidence_maturity": max(current.evidence_confidence, signal.importance * 0.7),
            "upside_asymmetry": current.asymmetry_rating,
        })
        stage = advance_stage(current.stage, infer_stage(signal.signal_type))
        action = recommend_action(stage, scores, market_repricing_pct=market_repricing_pct)
        now = utc_now()
        updated = replace(
            current,
            stage=stage,
            why_now=signal.description,
            evidence_confidence=scores.evidence_confidence,
            edge_conviction=scores.edge_conviction,
            asymmetry_rating=scores.asymmetry_rating,
            recommended_action=action,
            last_updated_at=now,
            metadata={**current.metadata, "market_repricing_pct": market_repricing_pct},
        )
        linked = replace(signal, linked_thesis_id=thesis_id)
        self.store.save_thesis(updated)
        self.store.append_signal(thesis_id, linked)
        self._journal(updated, f"Updated from {signal.signal_type.value}: {signal.description}")
        return updated

    def mark_consensus(self, thesis_id: str, reason: str) -> OpportunityThesis:
        current = self.store.get_thesis(thesis_id)
        if current is None:
            raise KeyError(f"Unknown thesis_id: {thesis_id}")
        if current.stage == OpportunityStage.BROKEN:
            raise ValueError("Broken theses are immutable; create a new thesis for a new setup.")
        now = utc_now()
        updated = replace(
            current,
            stage=OpportunityStage.CONSENSUS,
            recommended_action=OpportunityAction.DO_NOT_CHASE,
            why_now=reason,
            last_updated_at=now,
        )
        self.store.save_thesis(updated)
        self._journal(updated, f"Consensus reached: {reason}")
        return updated

    def break_thesis(self, thesis_id: str, reason: str) -> OpportunityThesis:
        current = self.store.get_thesis(thesis_id)
        if current is None:
            raise KeyError(f"Unknown thesis_id: {thesis_id}")
        now = utc_now()
        updated = replace(
            current,
            stage=OpportunityStage.BROKEN,
            recommended_action=OpportunityAction.EXIT,
            why_now=reason,
            last_updated_at=now,
        )
        self.store.save_thesis(updated)
        self._journal(updated, f"Thesis broken: {reason}")
        return updated
