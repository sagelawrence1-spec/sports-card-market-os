import pytest

from evidence_store import EvidenceStore


CARD_ID = "card-lineage-1"


def state(as_of, **overrides):
    value = {
        "card_id": CARD_ID,
        "last_updated": as_of,
        "fair_value": 100.0,
        "evidence_range": {"low": 95.0, "high": 105.0},
        "evidence_grade": "A",
        "confidence": 0.80,
        "accepted_sales_30d": 10,
        "accepted_sales_total": 10,
        "accepted_active_count": 2,
        "review_count": 0,
        "excluded_count": 0,
        "latest_sale_date": "2026-08-10",
        "action": None,
        "engine_classification": "EVIDENCE_READY",
        "blockers": [],
    }
    value.update(overrides)
    return value


def persist(store, as_of, **overrides):
    run_id = store.start_market_run(as_of, "test")
    persisted = store.save_market_state(run_id, state(as_of, **overrides))
    return run_id, persisted


def test_backfill_reconstructs_against_strictly_earlier_snapshot(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    first_run, _ = persist(store, "2026-08-10T12:00:00Z")
    future_run, _ = persist(store, "2026-08-12T12:00:00Z")

    backfill_run, backfill = persist(store, "2026-08-11T12:00:00Z")

    assert backfill["reconstruction"]["has_previous"] is True
    assert backfill["reconstruction"]["previous_as_of"] == "2026-08-10T12:00:00Z"
    assert backfill["lineage"] == {
        "run_id": backfill_run,
        "as_of": "2026-08-11T12:00:00Z",
        "previous_run_id": first_run,
        "previous_as_of": "2026-08-10T12:00:00Z",
    }
    assert backfill["lineage"]["previous_run_id"] != future_run


def test_previous_market_state_can_be_bounded_by_as_of(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    persist(store, "2026-08-10T12:00:00Z", fair_value=90.0)
    persist(store, "2026-08-12T12:00:00Z", fair_value=120.0)

    bounded = store.previous_market_state(CARD_ID, before_as_of="2026-08-11T12:00:00Z")
    latest = store.previous_market_state(CARD_ID)

    assert bounded["fair_value"] == 90.0
    assert latest["fair_value"] == 120.0


def test_state_timestamp_must_match_market_run_as_of(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    run_id = store.start_market_run("2026-08-10T12:00:00Z", "test")

    with pytest.raises(ValueError, match="last_updated must match market run as_of"):
        store.save_market_state(run_id, state("2026-08-11T12:00:00Z"))

    count = store.conn.execute("SELECT COUNT(*) FROM card_market_history").fetchone()[0]
    assert count == 0
