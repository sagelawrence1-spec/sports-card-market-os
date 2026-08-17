import json
from pathlib import Path

import pytest

from opportunity_engine import OpportunityEngine
from opportunity_ledger import OpportunityLedger
from opportunity_radar import evaluate_live_observation


FIXTURE = Path(__file__).parents[1] / "fixtures" / "opportunities" / "2026-08-16-joshua-baez.json"


def _candidate():
    engine = OpportunityEngine()
    payload = json.loads(FIXTURE.read_text())
    candidate = evaluate_live_observation(payload, engine=engine)
    return engine, candidate


def test_persists_original_live_call_and_provenance(tmp_path):
    engine, candidate = _candidate()
    store = OpportunityLedger(tmp_path / "opportunities.sqlite")
    store.persist_candidate(candidate, engine.ledger(candidate.thesis.thesis_id))

    row = store.get_call(candidate.thesis.thesis_id)
    assert row is not None
    assert row["schema_version"] == "opportunity-ledger.v1"
    assert row["decision"] == "WATCH_FOR_COMPS"
    assert row["market_price_verified"] == 0
    assert row["blocking_reason"] == "authoritative_market_repricing_unverified"
    assert row["thesis"]["player"] == "Joshua Baez"
    assert row["thesis"]["stage"] == "ACCELERATION"
    assert len(row["source_urls"]) >= 1
    assert len(row["events"]) == 1
    assert row["events"][0]["reason"] == "spark"


def test_identical_retry_is_idempotent(tmp_path):
    engine, candidate = _candidate()
    store = OpportunityLedger(tmp_path / "opportunities.sqlite")
    events = engine.ledger(candidate.thesis.thesis_id)
    store.persist_candidate(candidate, events)
    store.persist_candidate(candidate, events)
    assert len(store.list_calls()) == 1


def test_original_call_cannot_be_rewritten(tmp_path):
    engine, candidate = _candidate()
    store = OpportunityLedger(tmp_path / "opportunities.sqlite")
    events = engine.ledger(candidate.thesis.thesis_id)
    store.persist_candidate(candidate, events)

    object.__setattr__(candidate, "decision", "ADD")
    with pytest.raises(ValueError, match="immutable"):
        store.persist_candidate(candidate, events)


def test_rejects_cross_thesis_events(tmp_path):
    engine, candidate = _candidate()
    other_engine, other_candidate = _candidate()
    store = OpportunityLedger(tmp_path / "opportunities.sqlite")
    with pytest.raises(ValueError, match="identity mismatch"):
        store.persist_candidate(candidate, other_engine.ledger(other_candidate.thesis.thesis_id))
