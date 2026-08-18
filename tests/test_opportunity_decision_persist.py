from __future__ import annotations

import copy
import json

import pytest

from opportunity_decision_ledger import OpportunityDecisionLedger
from opportunity_decision_persist import main, persist_opportunity_decision_batch


def _packet(player_id: str, card_id: str) -> dict:
    return {
        "schema": "opportunity-decision-packet.v1",
        "player_id": player_id,
        "catalyst_at": "2026-08-18T12:00:00+00:00",
        "as_of": "2026-08-18T18:00:00+00:00",
        "card": {"card_id": card_id},
        "decision": "START_POSITION",
        "actionable": True,
    }


def _batch(*rows: dict) -> dict:
    return {"schema": "opportunity-decision-batch.v1", "results": list(rows)}


def test_persists_ready_packets_and_preserves_blockers(tmp_path):
    batch = _batch(
        {
            "player_id": "p1",
            "card_id": "c1",
            "decision_status": "READY",
            "packet": _packet("p1", "c1"),
        },
        {
            "player_id": "p2",
            "card_id": "c2",
            "decision_status": "BLOCKED",
            "blocking_reason": "MISSING_EXPORT",
        },
    )
    ledger_path = tmp_path / "decisions.sqlite"

    receipt = persist_opportunity_decision_batch(batch, ledger_path=ledger_path)

    assert receipt["schema"] == "opportunity-decision-persist.v1"
    assert receipt["persisted_count"] == 1
    assert receipt["preserved_non_ready_count"] == 1
    assert receipt["complete"] is True
    assert len(OpportunityDecisionLedger(ledger_path).list_packets()) == 1
    assert receipt["non_ready"][0]["blocking_reason"] == "MISSING_EXPORT"


def test_batch_persistence_is_atomic_on_immutable_conflict(tmp_path):
    ledger_path = tmp_path / "decisions.sqlite"
    ledger = OpportunityDecisionLedger(ledger_path)
    original = _packet("p1", "c1")
    ledger.persist_packet(original)

    conflicting = copy.deepcopy(original)
    conflicting["decision"] = "DO_NOT_CHASE"
    conflicting["actionable"] = False
    new_packet = _packet("p2", "c2")
    batch = _batch(
        {"decision_status": "READY", "packet": new_packet},
        {"decision_status": "READY", "packet": conflicting},
    )

    with pytest.raises(ValueError, match="immutable"):
        persist_opportunity_decision_batch(batch, ledger_path=ledger_path)

    assert ledger.list_packets() == (original,)


def test_conflicting_packets_inside_same_batch_write_nothing(tmp_path):
    ledger_path = tmp_path / "decisions.sqlite"
    first = _packet("p1", "c1")
    second = copy.deepcopy(first)
    second["decision"] = "DO_NOT_CHASE"
    second["actionable"] = False
    batch = _batch(
        {"decision_status": "READY", "packet": first},
        {"decision_status": "READY", "packet": second},
    )

    with pytest.raises(ValueError, match="conflicting"):
        persist_opportunity_decision_batch(batch, ledger_path=ledger_path)

    assert OpportunityDecisionLedger(ledger_path).list_packets() == ()


def test_exact_batch_retry_is_idempotent(tmp_path):
    ledger_path = tmp_path / "decisions.sqlite"
    batch = _batch({"decision_status": "READY", "packet": _packet("p1", "c1")})

    first = persist_opportunity_decision_batch(batch, ledger_path=ledger_path)
    second = persist_opportunity_decision_batch(copy.deepcopy(batch), ledger_path=ledger_path)

    assert first["decision_ids"] == second["decision_ids"]
    assert len(OpportunityDecisionLedger(ledger_path).list_packets()) == 1


def test_cli_persists_batch_and_writes_receipt(tmp_path):
    batch_path = tmp_path / "batch.json"
    ledger_path = tmp_path / "decisions.sqlite"
    output_path = tmp_path / "receipt.json"
    batch_path.write_text(
        json.dumps(_batch({"decision_status": "READY", "packet": _packet("p1", "c1")})),
        encoding="utf-8",
    )

    assert main(["--batch", str(batch_path), "--ledger", str(ledger_path), "-o", str(output_path)]) == 0
    receipt = json.loads(output_path.read_text(encoding="utf-8"))
    assert receipt["persisted_count"] == 1
    assert len(OpportunityDecisionLedger(ledger_path).list_packets()) == 1
