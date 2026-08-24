from datetime import date

import pytest

from recommendation_events import RecommendationEvent, RecommendationEventStore
from recommendation_journal import Recommendation, RecommendationJournal


def _recommendation() -> Recommendation:
    return Recommendation(
        observation_id="obs-1",
        card_id="card-1",
        as_of_date=date(2026, 8, 1),
        action="BUY",
        entry_price=100.0,
        fair_value=140.0,
        confidence=0.8,
        evidence_grade="A",
        thesis="mispriced scarcity",
        horizon_days=30,
    )


def _event(**overrides) -> RecommendationEvent:
    values = {
        "event_id": "evt-1",
        "observation_id": "obs-1",
        "as_of_date": date(2026, 8, 1),
        "horizon_days": 30,
        "event_type": "CLOSED",
        "occurred_at": date(2026, 8, 20),
        "reason": "target reached",
    }
    values.update(overrides)
    return RecommendationEvent(**values)


def test_lifecycle_event_is_append_only_and_does_not_rewrite_recommendation(tmp_path):
    path = tmp_path / "journal.sqlite"
    journal = RecommendationJournal(path)
    original = _recommendation()
    journal.upsert(original)
    events = RecommendationEventStore(path)

    events.append(_event())
    events.append(_event())

    assert journal.load() == [original]
    assert events.load() == [_event()]

    with pytest.raises(ValueError, match="immutable"):
        events.append(_event(reason="changed after publication"))


def test_invalidation_is_an_explicit_event(tmp_path):
    path = tmp_path / "journal.sqlite"
    journal = RecommendationJournal(path)
    journal.upsert(_recommendation())
    events = RecommendationEventStore(path)

    invalidated = _event(
        event_id="evt-invalid",
        event_type="INVALIDATED",
        occurred_at=date(2026, 8, 10),
        reason="identity resolution changed",
    )
    events.append(invalidated)

    assert events.load("obs-1") == [invalidated]
    assert journal.load()[0].thesis == "mispriced scarcity"


def test_lifecycle_event_requires_existing_recommendation(tmp_path):
    path = tmp_path / "journal.sqlite"
    RecommendationJournal(path)
    events = RecommendationEventStore(path)

    with pytest.raises(ValueError, match="existing recommendation"):
        events.append(_event())


def test_lifecycle_event_rejects_invalid_event_metadata(tmp_path):
    path = tmp_path / "journal.sqlite"
    journal = RecommendationJournal(path)
    journal.upsert(_recommendation())
    events = RecommendationEventStore(path)

    with pytest.raises(ValueError, match="event_type"):
        events.append(_event(event_type="UPDATED"))
    with pytest.raises(ValueError, match="predate"):
        events.append(_event(occurred_at=date(2026, 7, 31)))
    with pytest.raises(ValueError, match="reason"):
        events.append(_event(reason="  "))
