import json

import pytest

from evidence_store import EvidenceStore
from reconstruction import build_reconstruction_record
from reconstruction_history import persist_reconstruction_record, reconstruction_history


CARD_ID = "card-reconstruction-history"


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


def persist_state(store, as_of, **overrides):
    run_id = store.start_market_run(as_of, "test")
    persisted = store.save_market_state(run_id, state(as_of, **overrides))
    return run_id, persisted


def test_reconstruction_record_persists_with_exact_snapshot_lineage(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    first_run, first = persist_state(store, "2026-08-10T12:00:00Z")
    second_run, second = persist_state(
        store,
        "2026-08-11T12:00:00Z",
        fair_value=110.0,
        accepted_sales_30d=11,
        accepted_sales_total=11,
        latest_sale_date="2026-08-11",
    )

    first["run_id"] = first_run
    second["run_id"] = second_run
    record = build_reconstruction_record(first, second)
    persist_reconstruction_record(store.conn, record)

    rows = reconstruction_history(store.conn, CARD_ID)
    assert rows == [record]
    assert rows[0]["previous_run_id"] == first_run
    assert rows[0]["run_id"] == second_run


def test_reconstruction_history_is_append_only(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    first_run, first = persist_state(store, "2026-08-10T12:00:00Z")
    second_run, second = persist_state(store, "2026-08-11T12:00:00Z")
    first["run_id"] = first_run
    second["run_id"] = second_run
    record = build_reconstruction_record(first, second)

    persist_reconstruction_record(store.conn, record)
    with pytest.raises(ValueError, match="append-only"):
        persist_reconstruction_record(store.conn, record)

    assert len(reconstruction_history(store.conn, CARD_ID)) == 1


def test_reconstruction_record_cannot_reference_unpersisted_snapshot(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    run_id, current = persist_state(store, "2026-08-11T12:00:00Z")
    current["run_id"] = run_id
    record = build_reconstruction_record(None, current)
    record["previous_run_id"] = "missing-run"
    record["previous_as_of"] = "2026-08-10T12:00:00Z"

    with pytest.raises(ValueError, match="persisted market snapshots"):
        persist_reconstruction_record(store.conn, record)


def test_reconstruction_record_rejects_wrong_schema(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    run_id, current = persist_state(store, "2026-08-11T12:00:00Z")
    current["run_id"] = run_id
    record = build_reconstruction_record(None, current)
    record["schema"] = "market-reconstruction.v0"

    with pytest.raises(ValueError, match="unsupported reconstruction record schema"):
        persist_reconstruction_record(store.conn, record)


def test_stored_record_json_is_canonical_and_queryable(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    run_id, current = persist_state(store, "2026-08-11T12:00:00Z")
    current["run_id"] = run_id
    record = build_reconstruction_record(None, current)
    persist_reconstruction_record(store.conn, record)

    row = store.conn.execute(
        "SELECT record_id,card_id,run_id,as_of,record_json FROM market_reconstruction_history"
    ).fetchone()
    assert row["record_id"] == record["record_id"]
    assert row["card_id"] == CARD_ID
    assert row["run_id"] == run_id
    assert row["as_of"] == "2026-08-11T12:00:00Z"
    assert json.loads(row["record_json"]) == record
