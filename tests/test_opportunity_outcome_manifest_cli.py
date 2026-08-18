import json

from opportunity_outcome_manifest_cli import main


def _job():
    return {
        "packet": {
            "schema": "opportunity-decision-packet.v1",
            "player_id": "p1",
            "player": "Player One",
            "card": {"card_id": "c1", "label": "2026 Topps Chrome Player One #10"},
            "catalyst_at": "2026-08-10T12:00:00+00:00",
            "as_of": "2026-08-18T10:00:00+00:00",
            "decision": "START_POSITION",
            "actionable": True,
        },
        "entry_collection": {
            "schema": "opportunity-repricing-collection.v1",
            "player_id": "p1",
            "card_id": "c1",
            "verification": {"verified": True, "post_median": 100.0},
        },
    }


def test_cli_writes_mature_manifest(tmp_path):
    jobs_path = tmp_path / "jobs.json"
    output_path = tmp_path / "manifest.json"
    jobs_path.write_text(json.dumps([_job()]), encoding="utf-8")

    code = main([
        "--jobs", str(jobs_path),
        "--as-of", "2026-09-20T10:00:00+00:00",
        "--output", str(output_path),
    ])

    assert code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "opportunity-authoritative-outcome-manifest.v1"
    assert payload["mature_count"] == 1
    assert payload["items"][0]["status"] == "MATURE"


def test_cli_fails_closed_when_jobs_json_is_not_array(tmp_path, capsys):
    jobs_path = tmp_path / "jobs.json"
    jobs_path.write_text(json.dumps({"packet": {}}), encoding="utf-8")

    code = main([
        "--jobs", str(jobs_path),
        "--as-of", "2026-09-20T10:00:00+00:00",
    ])

    assert code == 2
    assert "jobs JSON must be an array" in capsys.readouterr().err
