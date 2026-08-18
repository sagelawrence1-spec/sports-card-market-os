from __future__ import annotations

import json

import opportunity_decision_batch as module
from opportunity_decision_batch import build_opportunity_decision_batch
from opportunity_decision_batch_cli import main


def _collection(player_id: str, card_id: str) -> dict:
    return {
        "schema": "opportunity-repricing-collection.v1",
        "player_id": player_id,
        "card_id": card_id,
    }


def _batch(*rows: dict) -> dict:
    return {
        "schema": "opportunity-repricing-batch.v1",
        "source_manifest_generated_at": "2026-08-18T16:00:00+00:00",
        "results": list(rows),
    }


def test_builds_packets_and_preserves_blockers(monkeypatch):
    def fake_packet(observation, collection):
        return {
            "schema": "opportunity-decision-packet.v1",
            "player_id": observation["player_id"],
            "decision": "START_POSITION",
            "actionable": True,
        }

    monkeypatch.setattr(module, "build_opportunity_decision_packet", fake_packet)
    batch = _batch(
        {
            "card_id": "card-1",
            "status": "COLLECTED",
            "artifact": _collection("player-1", "card-1"),
        },
        {
            "card_id": "card-2",
            "status": "MISSING_EXPORT",
            "csv_path": "/tmp/card-2.csv",
        },
    )

    result = build_opportunity_decision_batch(batch, observations=[{"player_id": "player-1"}])

    assert result["schema"] == "opportunity-decision-batch.v1"
    assert result["requested_count"] == 2
    assert result["packet_count"] == 1
    assert result["actionable_count"] == 1
    assert result["blocked_count"] == 1
    assert result["failed_count"] == 0
    assert result["ready"] is False
    assert result["results"][0]["decision_status"] == "READY"
    assert result["results"][1]["blocking_reason"] == "MISSING_EXPORT"


def test_missing_observation_fails_closed(monkeypatch):
    monkeypatch.setattr(module, "build_opportunity_decision_packet", lambda *_: (_ for _ in ()).throw(AssertionError()))
    batch = _batch(
        {
            "card_id": "card-1",
            "status": "COLLECTED",
            "artifact": _collection("player-1", "card-1"),
        }
    )

    result = build_opportunity_decision_batch(batch, observations=[])

    assert result["packet_count"] == 0
    assert result["blocked_count"] == 1
    assert result["results"][0]["blocking_reason"] == "MISSING_OBSERVATION"


def test_duplicate_observation_identity_is_rejected():
    batch = _batch()
    observations = [{"player_id": "player-1"}, {"player_id": "player-1"}]

    try:
        build_opportunity_decision_batch(batch, observations=observations)
    except ValueError as exc:
        assert "duplicate observation player_id" in str(exc)
    else:
        raise AssertionError("expected duplicate observation identity to fail")


def test_invalid_collection_artifact_is_reported_as_failure():
    batch = _batch(
        {
            "card_id": "card-1",
            "status": "COLLECTED",
            "artifact": {"schema": "wrong.v1", "player_id": "player-1"},
        }
    )

    result = build_opportunity_decision_batch(batch, observations=[{"player_id": "player-1"}])

    assert result["failed_count"] == 1
    assert result["results"][0]["blocking_reason"] == "INVALID_COLLECTION_ARTIFACT"


def test_cli_writes_decision_batch(tmp_path, monkeypatch):
    batch_path = tmp_path / "batch.json"
    observations_path = tmp_path / "observations.json"
    output_path = tmp_path / "decisions.json"
    batch_path.write_text(
        json.dumps(
            _batch(
                {
                    "card_id": "card-1",
                    "status": "MISSING_EXPORT",
                    "csv_path": "/tmp/card-1.csv",
                }
            )
        ),
        encoding="utf-8",
    )
    observations_path.write_text(json.dumps([]), encoding="utf-8")

    assert main(["--batch", str(batch_path), "--observations", str(observations_path), "-o", str(output_path)]) == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "opportunity-decision-batch.v1"
    assert payload["blocked_count"] == 1
