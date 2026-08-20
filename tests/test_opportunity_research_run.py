from __future__ import annotations

import hashlib
import json

import opportunity_research_run as run


def _manifest(filename: str = "card.csv"):
    return {
        "schema": "opportunity-repricing-collection-manifest.v1",
        "source_scan_generated_at": "2026-08-20T05:00:00+00:00",
        "items": [
            {
                "card_id": "card-1",
                "expected_export_filename": filename,
                "repricing_request": {"card_id": "card-1", "query": "player card"},
            }
        ],
    }


def test_research_run_composes_receipt_collection_decision_and_persistence(tmp_path, monkeypatch):
    csv_path = tmp_path / "card.csv"
    raw = b"header\nrow\n"
    csv_path.write_bytes(raw)

    monkeypatch.setattr(run, "build_receipt", lambda path, query="": {
        "schema": "product-research-receipt.v1",
        "source": {
            "filename": path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        },
        "query": query,
    })
    monkeypatch.setattr(run, "collect_manifest_batch", lambda manifest, assets, export_dir: {
        "schema": "opportunity-repricing-batch.v1",
        "ready": True,
        "results": [{"card_id": "card-1", "status": "COLLECTED"}],
    })
    monkeypatch.setattr(run, "build_opportunity_decision_batch", lambda batch, observations: {
        "schema": "opportunity-decision-batch.v1",
        "ready": True,
        "results": [{"card_id": "card-1", "decision_status": "READY", "packet": {"decision": "START_POSITION"}}],
    })
    monkeypatch.setattr(run, "persist_opportunity_decision_batch", lambda batch, ledger_path: {
        "schema": "opportunity-decision-persist.v1",
        "complete": True,
        "persisted_count": 1,
    })

    result = run.execute_opportunity_research_run(
        _manifest(),
        assets={"card-1": {"card_id": "card-1"}},
        observations=[{"player_id": "player-1"}],
        export_dir=tmp_path,
        ledger_path=tmp_path / "decisions.sqlite",
    )

    assert result["schema"] == "opportunity-research-run.v1"
    assert result["receipt_ready_count"] == 1
    assert result["missing_export_count"] == 0
    assert result["receipts"][0]["receipt"]["query"] == "player card"
    assert result["collection"]["ready"] is True
    assert result["decisions"]["ready"] is True
    assert result["persistence"]["persisted_count"] == 1
    assert result["complete"] is True


def test_research_run_fails_if_export_changes_after_receipt(tmp_path, monkeypatch):
    csv_path = tmp_path / "card.csv"
    raw = b"header\nrow\n"
    csv_path.write_bytes(raw)

    monkeypatch.setattr(run, "build_receipt", lambda path, query="": {
        "schema": "product-research-receipt.v1",
        "source": {
            "filename": path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        },
        "query": query,
    })

    def mutate_during_collection(manifest, assets, export_dir):
        csv_path.write_bytes(b"header\nROW\n")
        return {
            "schema": "opportunity-repricing-batch.v1",
            "ready": True,
            "results": [{"card_id": "card-1", "status": "COLLECTED"}],
        }

    monkeypatch.setattr(run, "collect_manifest_batch", mutate_during_collection)
    decision_called = False

    def build_decisions(batch, observations):
        nonlocal decision_called
        decision_called = True
        return {"schema": "opportunity-decision-batch.v1", "ready": True, "results": []}

    monkeypatch.setattr(run, "build_opportunity_decision_batch", build_decisions)

    try:
        run.execute_opportunity_research_run(
            _manifest(),
            assets={"card-1": {"card_id": "card-1"}},
            observations=[{"player_id": "player-1"}],
            export_dir=tmp_path,
        )
    except ValueError as exc:
        assert "changed after receipt" in str(exc)
    else:
        raise AssertionError("expected ValueError")

    assert decision_called is False


def test_research_run_rejects_parent_traversal_export_filename(tmp_path, monkeypatch):
    outside = tmp_path.parent / "outside.csv"
    outside.write_text("secret\n", encoding="utf-8")
    collection_called = False

    def collect(*args, **kwargs):
        nonlocal collection_called
        collection_called = True
        return {"schema": "opportunity-repricing-batch.v1", "ready": True, "results": []}

    monkeypatch.setattr(run, "collect_manifest_batch", collect)

    try:
        run.execute_opportunity_research_run(
            _manifest("../outside.csv"),
            assets={"card-1": {"card_id": "card-1"}},
            observations=[{"player_id": "player-1"}],
            export_dir=tmp_path,
        )
    except ValueError as exc:
        assert "plain filename within export_dir" in str(exc)
    else:
        raise AssertionError("expected ValueError")

    assert collection_called is False


def test_research_run_rejects_absolute_export_filename(tmp_path, monkeypatch):
    outside = tmp_path / "outside.csv"
    outside.write_text("secret\n", encoding="utf-8")
    monkeypatch.setattr(run, "collect_manifest_batch", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("collection must not run")))

    try:
        run.execute_opportunity_research_run(
            _manifest(str(outside.resolve())),
            assets={"card-1": {"card_id": "card-1"}},
            observations=[{"player_id": "player-1"}],
            export_dir=tmp_path,
        )
    except ValueError as exc:
        assert "plain filename within export_dir" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_research_run_keeps_missing_export_visible(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "collect_manifest_batch", lambda manifest, assets, export_dir: {
        "schema": "opportunity-repricing-batch.v1",
        "ready": False,
        "results": [{"card_id": "card-1", "status": "MISSING_EXPORT"}],
    })
    monkeypatch.setattr(run, "build_opportunity_decision_batch", lambda batch, observations: {
        "schema": "opportunity-decision-batch.v1",
        "ready": False,
        "results": [{"card_id": "card-1", "decision_status": "BLOCKED"}],
    })

    result = run.execute_opportunity_research_run(
        _manifest("missing.csv"),
        assets={"card-1": {"card_id": "card-1"}},
        observations=[{"player_id": "player-1"}],
        export_dir=tmp_path,
    )

    assert result["receipt_ready_count"] == 0
    assert result["missing_export_count"] == 1
    assert result["receipts"][0]["status"] == "MISSING_EXPORT"
    assert result["complete"] is False


def test_cli_writes_one_combined_artifact(tmp_path, monkeypatch):
    manifest_path = tmp_path / "manifest.json"
    assets_path = tmp_path / "assets.json"
    observations_path = tmp_path / "observations.json"
    output_path = tmp_path / "run.json"
    manifest_path.write_text(json.dumps(_manifest("missing.csv")), encoding="utf-8")
    assets_path.write_text(json.dumps({"card-1": {"card_id": "card-1"}}), encoding="utf-8")
    observations_path.write_text(json.dumps([{"player_id": "player-1"}]), encoding="utf-8")

    monkeypatch.setattr(run, "execute_opportunity_research_run", lambda *args, **kwargs: {
        "schema": "opportunity-research-run.v1",
        "complete": False,
        "requested_count": 1,
    })

    code = run.main([
        "--manifest", str(manifest_path),
        "--assets", str(assets_path),
        "--observations", str(observations_path),
        "--exports", str(tmp_path),
        "--output", str(output_path),
    ])

    assert code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "opportunity-research-run.v1"
    assert payload["requested_count"] == 1


def test_research_run_rejects_wrong_manifest_schema(tmp_path):
    try:
        run.execute_opportunity_research_run(
            {"schema": "wrong", "items": []},
            assets={},
            observations=[],
            export_dir=tmp_path,
        )
    except ValueError as exc:
        assert "unsupported collection manifest schema" in str(exc)
    else:
        raise AssertionError("expected ValueError")