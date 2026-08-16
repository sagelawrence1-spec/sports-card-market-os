import json

import pytest

from evidence_store import EvidenceStore


def market_state(**overrides):
    state={
        "card_id":"card-1",
        "last_updated":"2026-08-16T10:00:00Z",
        "fair_value":100.0,
        "evidence_range":{"low":90.0,"high":110.0},
        "evidence_grade":"A",
        "confidence":0.85,
        "accepted_sales_30d":8,
        "accepted_sales_total":8,
        "accepted_active_count":2,
        "review_count":0,
        "excluded_count":1,
        "latest_sale_date":"2026-08-15",
        "lowest_ask":105.0,
        "median_ask":110.0,
        "action":"BUY",
        "thesis":"test thesis",
    }
    state.update(overrides)
    return state


def test_market_state_requires_real_running_run(tmp_path):
    store=EvidenceStore(tmp_path / "market.db")

    with pytest.raises(ValueError,match="persisted market run"):
        store.save_market_state("missing-run",market_state())


def test_finished_run_cannot_receive_more_history(tmp_path):
    store=EvidenceStore(tmp_path / "market.db")
    run_id=store.start_market_run("2026-08-16T10:00:00Z","test")
    store.finish_market_run(run_id,"success")

    with pytest.raises(ValueError,match="while the market run is running"):
        store.save_market_state(run_id,market_state())


def test_run_card_snapshot_is_append_only(tmp_path):
    store=EvidenceStore(tmp_path / "market.db")
    run_id=store.start_market_run("2026-08-16T10:00:00Z","test")
    original=market_state(fair_value=100.0)
    store.save_market_state(run_id,original)

    with pytest.raises(ValueError,match="append-only"):
        store.save_market_state(run_id,market_state(fair_value=150.0))

    row=store.conn.execute(
        "SELECT fair_value,state_json FROM card_market_history WHERE run_id=? AND card_id=?",
        (run_id,"card-1"),
    ).fetchone()
    assert row["fair_value"] == 100.0
    assert json.loads(row["state_json"])["fair_value"] == 100.0


def test_persisting_history_does_not_mutate_caller_state(tmp_path):
    store=EvidenceStore(tmp_path / "market.db")
    run_id=store.start_market_run("2026-08-16T10:00:00Z","test")
    state=market_state()

    store.save_market_state(run_id,state)

    assert "reconstruction" not in state
    assert "blockers" not in state
