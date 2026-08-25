import json
import sqlite3

import pytest

from recommendation_journal import RecommendationJournal, capture_recommendations


def _contract(*, thesis_type="CATALYST", stage="ENTRY", evidence_price=100.0):
    return {
        "generated_at": "2026-08-24T12:00:00+00:00",
        "items": [
            {
                "observation_id": "obs-1",
                "card_id": "card-1",
                "action": "BUY",
                "fair_value": 140.0,
                "confidence": 0.8,
                "evidence_grade": "A",
                "thesis": "Scheduled catalyst remains underpriced.",
                "thesis_type": thesis_type,
                "stage": stage,
                "card_expressions": [
                    {"card_id": "card-1", "priority": 1, "role": "primary"},
                    {"card_id": "card-2", "priority": 2, "role": "secondary"},
                ],
                "evidence_ledger": {
                    "accepted": [
                        {
                            "evidence_id": "sale-1",
                            "event_date": "2026-08-24",
                            "price": evidence_price,
                            "currency": "USD",
                            "used_in_valuation": True,
                            "source": "ebay_product_research",
                        }
                    ]
                },
            }
        ],
    }


def test_capture_freezes_rich_decision_context(tmp_path):
    journal = RecommendationJournal(tmp_path / "recommendations.sqlite")

    assert capture_recommendations(journal, _contract()) == 1
    row = journal.load()[0]
    snapshot = json.loads(row.decision_snapshot)

    assert snapshot["thesis_type"] == "CATALYST"
    assert snapshot["lifecycle_stage"] == "ENTRY"
    assert snapshot["card_expressions"][1]["card_id"] == "card-2"
    assert snapshot["evidence_snapshot"]["accepted"][0]["evidence_id"] == "sale-1"


def test_decision_snapshot_is_immutable_after_publication(tmp_path):
    journal = RecommendationJournal(tmp_path / "recommendations.sqlite")
    capture_recommendations(journal, _contract())

    with pytest.raises(ValueError, match="Published recommendation inputs are immutable"):
        capture_recommendations(journal, _contract(thesis_type="QUANT"))

    with pytest.raises(ValueError, match="Published recommendation inputs are immutable"):
        capture_recommendations(journal, _contract(evidence_price=101.0))


def test_existing_journal_schema_migrates_without_rewriting_legacy_rows(tmp_path):
    path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE recommendation_journal (
                observation_id TEXT NOT NULL,
                card_id TEXT NOT NULL,
                as_of_date TEXT NOT NULL,
                action TEXT NOT NULL,
                entry_price REAL NOT NULL,
                fair_value REAL NOT NULL,
                confidence REAL NOT NULL,
                evidence_grade TEXT NOT NULL,
                thesis TEXT NOT NULL,
                horizon_days INTEGER NOT NULL,
                realized_price REAL,
                realized_at TEXT,
                PRIMARY KEY(observation_id,as_of_date,horizon_days)
            )
        """)
        conn.execute(
            "INSERT INTO recommendation_journal VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("legacy", "card-legacy", "2026-08-01", "BUY", 100.0, 120.0, 0.7, "B", "legacy thesis", 30, None, None),
        )

    journal = RecommendationJournal(path)
    row = journal.load()[0]
    assert row.observation_id == "legacy"
    assert row.decision_snapshot == "{}"
