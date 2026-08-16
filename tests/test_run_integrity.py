import json

import pytest

from evidence_store import EvidenceStore
from run_integrity import audit_market_run_reconstruction


def state(card_id, as_of):
    return {
        "card_id": card_id,
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


def test_clean_run_has_complete_snapshot_and_reconstruction_coverage(tmp_path):
    store = EvidenceStore(tmp_path / "market.sqlite")
    as_of = "2026-08-16T12:00:00Z"
    run_id = store.start_market_run(as_of, "test")
    store.save_market_state(run_id, state("card-a", as_of))
    store.save_market_state(run_id, state("card-b", as_of))

    audit = audit_market_run_reconstruction(store.conn, run_id, ["card-a", "card-b"])

    assert audit["status"] == "healthy"
    assert audit["expected_cards"] == 2
    assert audit["persisted_snapshots"] == 2
    assert audit["persisted_reconstructions"] == 2
    assert not any(audit["issues"].values())


def test_missing_expected_snapshot_fails_closed(tmp_path):
    store = EvidenceStore(tmp_path / "market.sqlite")
    as_of = "2026-08-16T12:00:00Z"
    run_id = store.start_market_run(as_of, "test")
    store.save_market_state(run_id, state("card-a", as_of))

    audit = audit_market_run_reconstruction(store.conn, run_id, ["card-a", "card-b"])

    assert audit["status"] == "failed"
    assert audit["issues"]["missing_snapshots"] == ["card-b"]


def test_missing_reconstruction_record_fails_closed(tmp_path):
    store = EvidenceStore(tmp_path / "market.sqlite")
    as_of = "2026-08-16T12:00:00Z"
    run_id = store.start_market_run(as_of, "test")
    store.save_market_state(run_id, state("card-a", as_of))
    store.conn.execute(
        "DELETE FROM market_reconstruction_history WHERE run_id=? AND card_id=?",
        (run_id, "card-a"),
    )
    store.conn.commit()

    audit = audit_market_run_reconstruction(store.conn, run_id, ["card-a"])

    assert audit["status"] == "failed"
    assert audit["issues"]["missing_reconstructions"] == ["card-a"]


def test_reconstruction_payload_column_disagreement_fails_closed(tmp_path):
    store = EvidenceStore(tmp_path / "market.sqlite")
    as_of = "2026-08-16T12:00:00Z"
    run_id = store.start_market_run(as_of, "test")
    store.save_market_state(run_id, state("card-a", as_of))
    row = store.conn.execute(
        "SELECT record_id,record_json FROM market_reconstruction_history WHERE run_id=? AND card_id=?",
        (run_id, "card-a"),
    ).fetchone()
    payload = json.loads(row["record_json"])
    payload["card_id"] = "different-card"
    store.conn.execute(
        "UPDATE market_reconstruction_history SET record_json=? WHERE record_id=?",
        (json.dumps(payload, sort_keys=True), row["record_id"]),
    )
    store.conn.commit()

    audit = audit_market_run_reconstruction(store.conn, run_id, ["card-a"])

    assert audit["status"] == "failed"
    assert audit["issues"]["malformed_reconstructions"] == ["card-a"]


def test_expected_card_ids_must_be_unique_and_nonblank(tmp_path):
    store = EvidenceStore(tmp_path / "market.sqlite")
    run_id = store.start_market_run("2026-08-16T12:00:00Z", "test")

    with pytest.raises(ValueError, match="unique"):
        audit_market_run_reconstruction(store.conn, run_id, ["card-a", "card-a"])
    with pytest.raises(ValueError, match="blank"):
        audit_market_run_reconstruction(store.conn, run_id, ["card-a", " "])
