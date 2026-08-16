import pytest

import evidence_store as evidence_store_module
from evidence_store import EvidenceStore


CARD_ID = "card-reconstruction-integration"


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


def test_save_market_state_automatically_persists_reconstruction_history(tmp_path):
    store = EvidenceStore(tmp_path / "market.sqlite")
    first_run, first = persist(store, "2026-08-10T12:00:00Z")
    second_run, second = persist(
        store,
        "2026-08-11T12:00:00Z",
        fair_value=110.0,
        accepted_sales_total=11,
        accepted_sales_30d=11,
        latest_sale_date="2026-08-11",
    )

    history = store.reconstruction_history(CARD_ID)

    assert len(history) == 2
    assert history[0]["run_id"] == first_run
    assert history[0]["previous_run_id"] is None
    assert history[1]["run_id"] == second_run
    assert history[1]["previous_run_id"] == first_run
    assert history[1]["delta"]["accepted_sales_delta"] == 1
    assert first["run_id"] == first_run
    assert second["run_id"] == second_run


def test_snapshot_and_reconstruction_record_commit_atomically(tmp_path, monkeypatch):
    store = EvidenceStore(tmp_path / "market.sqlite")
    run_id = store.start_market_run("2026-08-10T12:00:00Z", "test")

    def fail_reconstruction(*args, **kwargs):
        raise RuntimeError("forced reconstruction persistence failure")

    monkeypatch.setattr(
        evidence_store_module,
        "persist_reconstruction_record",
        fail_reconstruction,
    )

    with pytest.raises(RuntimeError, match="forced reconstruction persistence failure"):
        store.save_market_state(run_id, state("2026-08-10T12:00:00Z"))

    snapshot_count = store.conn.execute(
        "SELECT COUNT(*) FROM card_market_history WHERE run_id=? AND card_id=?",
        (run_id, CARD_ID),
    ).fetchone()[0]
    reconstruction_count = store.conn.execute(
        "SELECT COUNT(*) FROM market_reconstruction_history WHERE run_id=? AND card_id=?",
        (run_id, CARD_ID),
    ).fetchone()[0]

    assert snapshot_count == 0
    assert reconstruction_count == 0


def test_reconstruction_history_uses_backfill_predecessor_not_future_snapshot(tmp_path):
    store = EvidenceStore(tmp_path / "market.sqlite")
    first_run, _ = persist(store, "2026-08-10T12:00:00Z")
    future_run, _ = persist(store, "2026-08-12T12:00:00Z", fair_value=120.0)
    backfill_run, _ = persist(store, "2026-08-11T12:00:00Z", fair_value=105.0)

    history = store.reconstruction_history(CARD_ID)
    backfill = next(record for record in history if record["run_id"] == backfill_run)

    assert backfill["previous_run_id"] == first_run
    assert backfill["previous_run_id"] != future_run
    assert backfill["previous_as_of"] == "2026-08-10T12:00:00Z"
