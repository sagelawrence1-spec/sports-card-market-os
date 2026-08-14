import sqlite3

import pytest

from evidence_store import EvidenceStore
from routing_accuracy import RoutingAccuracyStore, RoutingAuditPolicy, routing_accuracy_summary


def _seed(path, rows):
    EvidenceStore(path)
    with sqlite3.connect(path) as conn:
        for evidence_id, card_id, status in rows:
            conn.execute(
                '''INSERT INTO source_evidence(
                  evidence_id,provider,record_type,source_item_id,card_id,query,title,
                  price,currency,event_date,url,match_score,match_status,match_reason,
                  match_diagnostics_json,raw_payload_json,run_id)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (
                    evidence_id,"ebay_product_research","sold",evidence_id,card_id,
                    "test","test title",100.0,"USD","2026-08-01","",95.0,
                    status,"test","{}","{}",None,
                ),
            )


def test_false_auto_accept_blocks_production(tmp_path):
    db = tmp_path / "market.sqlite"
    _seed(db, [("e1","card-a","accepted"),("e2","card-b","accepted")])
    labels = RoutingAccuracyStore(db)
    labels.label("e1",reviewer_id="r1",expected_card_id="card-a",is_relevant=True)
    labels.label("e2",reviewer_id="r1",expected_card_id="card-c",is_relevant=True)
    summary = routing_accuracy_summary(
        db,
        policy=RoutingAuditPolicy(min_labeled_rows=2,min_auto_accept_precision=0.99,max_review_rate=1.0),
    )
    assert summary["false_accepts"] == 1
    assert summary["auto_accept_precision"] == 0.5
    assert summary["production_ready"] is False
    assert "false_accepts_observed" in summary["blockers"]


def test_clean_but_small_sample_does_not_unlock_production(tmp_path):
    db = tmp_path / "market.sqlite"
    _seed(db, [("e1","card-a","accepted")])
    labels = RoutingAccuracyStore(db)
    labels.label("e1",reviewer_id="r1",expected_card_id="card-a",is_relevant=True)
    summary = routing_accuracy_summary(db,policy=RoutingAuditPolicy(min_labeled_rows=10))
    assert summary["auto_accept_precision"] == 1.0
    assert summary["production_ready"] is False
    assert summary["blockers"] == ["labeled_sample_too_small"]


def test_review_rate_ceiling_and_positive_recall_are_measured(tmp_path):
    db = tmp_path / "market.sqlite"
    _seed(db, [("e1","card-a","accepted"),("e2","card-b","review"),("e3","card-c","rejected")])
    labels = RoutingAccuracyStore(db)
    labels.label("e1",reviewer_id="r1",expected_card_id="card-a",is_relevant=True)
    labels.label("e2",reviewer_id="r1",expected_card_id="card-b",is_relevant=True)
    labels.label("e3",reviewer_id="r1",expected_card_id=None,is_relevant=False)
    summary = routing_accuracy_summary(
        db,
        policy=RoutingAuditPolicy(min_labeled_rows=3,max_review_rate=0.20),
    )
    assert summary["positive_recall"] == 1.0
    assert summary["review_rate"] == pytest.approx(1/3)
    assert "review_rate_above_ceiling" in summary["blockers"]


def test_conflicting_reviewer_labels_are_excluded_from_consensus(tmp_path):
    db = tmp_path / "market.sqlite"
    _seed(db, [("e1","card-a","accepted")])
    labels = RoutingAccuracyStore(db)
    labels.label("e1",reviewer_id="r1",expected_card_id="card-a",is_relevant=True)
    labels.label("e1",reviewer_id="r2",expected_card_id="card-b",is_relevant=True)
    summary = routing_accuracy_summary(
        db,
        policy=RoutingAuditPolicy(min_labeled_rows=1),
        min_reviewers=2,
    )
    assert summary["labeled_rows"] == 0
    assert summary["production_ready"] is False


def test_label_requires_existing_evidence_and_card_for_relevant_rows(tmp_path):
    db = tmp_path / "market.sqlite"
    _seed(db, [("e1","card-a","review")])
    labels = RoutingAccuracyStore(db)
    with pytest.raises(KeyError):
        labels.label("missing",reviewer_id="r1",expected_card_id="card-a",is_relevant=True)
    with pytest.raises(ValueError):
        labels.label("e1",reviewer_id="r1",expected_card_id=None,is_relevant=True)
