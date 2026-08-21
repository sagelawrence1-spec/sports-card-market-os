"""Persistent, point-in-time journal for published capital recommendations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
import sqlite3
import statistics
from typing import Any, Mapping

from market_contract import PUBLIC_ACTIONS


def _day(value: str) -> date:
    return datetime.fromisoformat(str(value)[:10]).date()


def _as_of(item: Mapping[str, Any], contract: Mapping[str, Any]) -> date:
    value = item.get("last_updated") or contract.get("generated_at")
    if not value:
        raise ValueError("Recommendation journaling requires a point-in-time timestamp.")
    return _day(value)


def _accepted_sales(item: Mapping[str, Any]) -> list[tuple[date, float]]:
    rows=[]
    for raw in (item.get("evidence_ledger") or {}).get("accepted") or []:
        if not raw.get("used_in_valuation"):
            continue
        if str(raw.get("currency") or "").upper()!="USD":
            continue
        try:
            sold=_day(raw["event_date"])
            price=float(raw["price"])
        except (KeyError,TypeError,ValueError):
            continue
        if price>0:
            rows.append((sold,price))
    return rows


@dataclass(frozen=True)
class Recommendation:
    observation_id: str
    card_id: str
    as_of_date: date
    action: str
    entry_price: float
    fair_value: float
    confidence: float
    evidence_grade: str
    thesis: str
    horizon_days: int
    realized_price: float | None=None
    realized_at: date | None=None

    @property
    def horizon_end(self) -> date:
        return self.as_of_date+timedelta(days=self.horizon_days)


class RecommendationJournal:
    def __init__(self,database_path: str):
        self.database_path=str(database_path)
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS recommendation_journal (
                    observation_id TEXT NOT NULL,
                    card_id TEXT NOT NULL,
                    as_of_date TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    fair_value REAL NOT NULL,
                    confidence REAL NOT NULL,
                    evidence_grade TEXT NOT NULL,
                    thesis TEXT NOT NULL,
                    horizon_days INTEGER NOT NULL,
                    realized_price REAL,
                    realized_at TEXT,
                    PRIMARY KEY(observation_id,as_of_date,horizon_days)
                )
            """)

    def _connect(self):
        conn=sqlite3.connect(self.database_path)
        conn.row_factory=sqlite3.Row
        return conn

    @staticmethod
    def _decision_fields(rec: Recommendation) -> tuple[Any, ...]:
        return (
            rec.card_id,
            rec.action,
            rec.entry_price,
            rec.fair_value,
            rec.confidence,
            rec.evidence_grade,
            rec.thesis,
        )

    @staticmethod
    def _row_decision_fields(row: sqlite3.Row) -> tuple[Any, ...]:
        return (
            row["card_id"],
            row["action"],
            row["entry_price"],
            row["fair_value"],
            row["confidence"],
            row["evidence_grade"],
            row["thesis"],
        )

    def upsert(self,rec: Recommendation) -> None:
        if (rec.realized_price is None) != (rec.realized_at is None):
            raise ValueError("Recommendation outcomes require both realized price and realized timestamp.")
        key=(rec.observation_id,rec.as_of_date.isoformat(),rec.horizon_days)
        with self._connect() as conn:
            existing=conn.execute("""
                SELECT * FROM recommendation_journal
                WHERE observation_id=? AND as_of_date=? AND horizon_days=?
            """,key).fetchone()
            if existing is None:
                conn.execute("""
                    INSERT INTO recommendation_journal VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,(
                    rec.observation_id,rec.card_id,rec.as_of_date.isoformat(),rec.action,
                    rec.entry_price,rec.fair_value,rec.confidence,rec.evidence_grade,
                    rec.thesis,rec.horizon_days,rec.realized_price,
                    rec.realized_at.isoformat() if rec.realized_at else None,
                ))
                return

            if self._row_decision_fields(existing) != self._decision_fields(rec):
                raise ValueError("Published recommendation inputs are immutable.")

            existing_price=existing["realized_price"]
            existing_at=existing["realized_at"]
            incoming_at=rec.realized_at.isoformat() if rec.realized_at else None
            if existing_price is None and existing_at is None:
                if rec.realized_price is None:
                    return
                conn.execute("""
                    UPDATE recommendation_journal
                    SET realized_price=?, realized_at=?
                    WHERE observation_id=? AND as_of_date=? AND horizon_days=?
                """,(rec.realized_price,incoming_at,*key))
                return

            if existing_price != rec.realized_price or existing_at != incoming_at:
                raise ValueError("Settled recommendation outcomes are immutable.")

    def load(self) -> list[Recommendation]:
        with self._connect() as conn:
            rows=conn.execute("SELECT * FROM recommendation_journal ORDER BY as_of_date,observation_id").fetchall()
        return [Recommendation(
            observation_id=row["observation_id"],card_id=row["card_id"],
            as_of_date=date.fromisoformat(row["as_of_date"]),action=row["action"],
            entry_price=row["entry_price"],fair_value=row["fair_value"],
            confidence=row["confidence"],evidence_grade=row["evidence_grade"],
            thesis=row["thesis"],horizon_days=row["horizon_days"],
            realized_price=row["realized_price"],
            realized_at=date.fromisoformat(row["realized_at"]) if row["realized_at"] else None,
        ) for row in rows]


def capture_recommendations(
    journal: RecommendationJournal,
    contract: Mapping[str,Any],
    *,
    horizon_days: int=30,
) -> int:
    if horizon_days<=0:
        raise ValueError("Recommendation horizon must be positive.")
    captured=0
    for item in contract.get("items") or []:
        action=item.get("action")
        fair_value=item.get("fair_value")
        if action not in PUBLIC_ACTIONS or fair_value is None:
            continue
        as_of=_as_of(item,contract)
        eligible=[(sold,price) for sold,price in _accepted_sales(item) if sold<=as_of]
        if not eligible:
            continue
        latest_day=max(sold for sold,_ in eligible)
        entry_price=float(statistics.median(price for sold,price in eligible if sold==latest_day))
        confidence=float(item.get("confidence") or 0.0)
        if confidence>1:
            confidence/=100.0
        journal.upsert(Recommendation(
            observation_id=str(item.get("observation_id") or f"{item['card_id']}:{as_of}"),
            card_id=str(item["card_id"]),as_of_date=as_of,action=action,
            entry_price=entry_price,fair_value=float(fair_value),
            confidence=max(0.0,min(1.0,confidence)),
            evidence_grade=str(item.get("evidence_grade") or "F"),
            thesis=str(item.get("thesis") or ""),horizon_days=int(horizon_days),
        ))
        captured+=1
    return captured


def settle_outcomes(journal: RecommendationJournal,contract: Mapping[str,Any]) -> int:
    items={str(item.get("card_id")):item for item in contract.get("items") or []}
    settled=0
    for rec in journal.load():
        if rec.realized_price is not None:
            continue
        item=items.get(rec.card_id)
        if not item:
            continue
        evaluation_date=_as_of(item,contract)
        if rec.horizon_end>evaluation_date:
            continue
        eligible=[
            (sold,price) for sold,price in _accepted_sales(item)
            if rec.horizon_end<=sold<=evaluation_date
        ]
        if not eligible:
            continue
        first_day=min(sold for sold,_ in eligible)
        realized=float(statistics.median(price for sold,price in eligible if sold==first_day))
        journal.upsert(replace(rec,realized_price=realized,realized_at=first_day))
        settled+=1
    return settled


def outcome_summary(journal: RecommendationJournal) -> dict[str,Any]:
    rows=[row for row in journal.load() if row.realized_price is not None]
    if not rows:
        return {"settled":0,"hit_rate":None,"median_return":None}
    signed_returns=[]
    hits=0
    for row in rows:
        change=(row.realized_price-row.entry_price)/row.entry_price
        signed=-change if row.action in {"TRIM","SELL"} else change
        signed_returns.append(signed)
        hits+=int(signed>0)
    return {
        "settled":len(rows),
        "hit_rate":hits/len(rows),
        "median_return":float(statistics.median(signed_returns)),
    }
