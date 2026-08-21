from dataclasses import replace
from datetime import date

import pytest

from recommendation_journal import Recommendation, RecommendationJournal


def _recommendation(**overrides):
    values={
        "observation_id":"obs-1",
        "card_id":"card-1",
        "as_of_date":date(2026,1,1),
        "action":"BUY",
        "entry_price":100.0,
        "fair_value":125.0,
        "confidence":0.8,
        "evidence_grade":"A",
        "thesis":"mispriced relative to evidence",
        "horizon_days":30,
    }
    values.update(overrides)
    return Recommendation(**values)


def test_identical_publish_retry_is_idempotent(tmp_path):
    journal=RecommendationJournal(tmp_path/"market.sqlite")
    rec=_recommendation()
    journal.upsert(rec)
    journal.upsert(rec)
    assert journal.load()==[rec]


def test_published_decision_inputs_cannot_be_rewritten(tmp_path):
    journal=RecommendationJournal(tmp_path/"market.sqlite")
    rec=_recommendation()
    journal.upsert(rec)
    for changed in (
        replace(rec,action="SELL"),
        replace(rec,entry_price=101.0),
        replace(rec,fair_value=140.0),
        replace(rec,confidence=0.95),
        replace(rec,evidence_grade="B"),
        replace(rec,thesis="rewritten with hindsight"),
        replace(rec,card_id="card-2"),
    ):
        with pytest.raises(ValueError,match="immutable"):
            journal.upsert(changed)
    assert journal.load()==[rec]


def test_outcome_can_be_completed_once_but_not_rewritten(tmp_path):
    journal=RecommendationJournal(tmp_path/"market.sqlite")
    rec=_recommendation()
    journal.upsert(rec)
    settled=replace(rec,realized_price=130.0,realized_at=date(2026,2,1))
    journal.upsert(settled)
    journal.upsert(settled)
    with pytest.raises(ValueError,match="outcomes are immutable"):
        journal.upsert(replace(rec,realized_price=90.0,realized_at=date(2026,2,2)))
    with pytest.raises(ValueError,match="outcomes are immutable"):
        journal.upsert(rec)
    assert journal.load()==[settled]


def test_partial_outcome_is_rejected(tmp_path):
    journal=RecommendationJournal(tmp_path/"market.sqlite")
    with pytest.raises(ValueError,match="both realized price and realized timestamp"):
        journal.upsert(_recommendation(realized_price=130.0))
    with pytest.raises(ValueError,match="both realized price and realized timestamp"):
        journal.upsert(_recommendation(realized_at=date(2026,2,1)))
