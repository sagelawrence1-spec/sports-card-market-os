import pytest

from evidence_store import EvidenceStore
from market_pipeline import PipelineResult
from market_runner import enforce_completed_run_integrity


def _state(card_id="card-1", as_of="2026-08-16T10:00:00Z"):
    return {
        "card_id":card_id,
        "last_updated":as_of,
        "fair_value":100.0,
        "evidence_range":{"low":90.0,"high":110.0},
        "evidence_grade":"A",
        "confidence":0.9,
        "accepted_sales_30d":8,
        "accepted_sales_total":8,
        "accepted_active_count":2,
        "review_count":0,
        "excluded_count":0,
        "latest_sale_date":"2026-08-15",
        "lowest_ask":105.0,
        "median_ask":110.0,
        "action":None,
        "thesis":"test",
        "blockers":[],
    }


def _result(run_id, status="complete"):
    return PipelineResult(
        run_id=run_id,
        contract={"source":{"provenance":{}},"items":[]},
        status=status,
        errors=(),
    )


def test_completed_run_keeps_complete_status_when_history_is_healthy(tmp_path):
    store=EvidenceStore(tmp_path / "market.db")
    run_id=store.start_market_run("2026-08-16T10:00:00Z","test")
    store.save_market_state(run_id,_state())
    store.finish_market_run(run_id,"complete")
    result=_result(run_id)

    audit=enforce_completed_run_integrity(store,result,[{"card_id":"card-1"}])

    assert audit["status"] == "healthy"
    assert result.contract["run_integrity"] == audit
    assert result.contract["source"]["provenance"]["run_integrity"] == audit
    row=store.conn.execute("SELECT status FROM market_runs WHERE run_id=?",(run_id,)).fetchone()
    assert row["status"] == "complete"


def test_completed_run_is_downgraded_when_expected_history_is_missing(tmp_path):
    store=EvidenceStore(tmp_path / "market.db")
    run_id=store.start_market_run("2026-08-16T10:00:00Z","test")
    store.finish_market_run(run_id,"complete")
    result=_result(run_id)

    with pytest.raises(RuntimeError,match="run-integrity audit"):
        enforce_completed_run_integrity(store,result,[{"card_id":"card-1"}])

    row=store.conn.execute(
        "SELECT status,metadata_json FROM market_runs WHERE run_id=?",
        (run_id,),
    ).fetchone()
    assert row["status"] == "history_integrity_failed"
    assert result.contract["run_integrity"]["issues"]["missing_snapshots"] == ["card-1"]


def test_noncomplete_run_does_not_require_history_integrity_audit(tmp_path):
    store=EvidenceStore(tmp_path / "market.db")
    result=_result("not-persisted",status="blocked_sold_source")

    assert enforce_completed_run_integrity(store,result,[{"card_id":"card-1"}]) is None
    assert "run_integrity" not in result.contract
