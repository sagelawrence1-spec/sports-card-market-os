import csv

import pytest

from opportunity_outcome_manifest_run import run_authoritative_outcome_manifest


def _packet(card_id="c1", *, actionable=True, decision="START_POSITION"):
    return {
        "schema": "opportunity-decision-packet.v1",
        "player_id": "p1",
        "player": "Player One",
        "card": {"card_id": card_id, "label": "2026 Topps Chrome Player One #10"},
        "catalyst_at": "2026-08-10T12:00:00+00:00",
        "as_of": "2026-08-18T10:00:00+00:00",
        "decision": decision,
        "actionable": actionable,
    }


def _entry(card_id="c1"):
    return {
        "schema": "opportunity-repricing-collection.v1",
        "player_id": "p1",
        "card_id": card_id,
        "verification": {
            "verified": True,
            "post_median": 100.0,
            "catalyst_at": "2026-08-10T12:00:00+00:00",
            "as_of": "2026-08-18T10:00:00+00:00",
        },
    }


def _asset(card_id="c1"):
    return {
        "card_id": card_id,
        "player": "Player One",
        "year": 2026,
        "manufacturer": "Topps",
        "set_name": "Topps Chrome",
        "card_number": "10",
        "parallel": "base",
        "autograph": 0,
    }


def _write_export(tmp_path, filename):
    path = tmp_path / filename
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Title", "Sold Price", "Sold Date", "Item ID", "Currency"])
        writer.writeheader()
        for idx, price in enumerate((120, 130, 140), 1):
            writer.writerow({
                "Title": "2026 Topps Chrome Player One #10",
                "Sold Price": f"${price}",
                "Sold Date": f"2026-09-{17 + idx:02d}",
                "Item ID": str(idx),
                "Currency": "USD",
            })


def _manifest(*, status="MATURE", mature_count=1):
    packet = _packet()
    return {
        "schema": "opportunity-authoritative-outcome-manifest.v1",
        "as_of": "2026-09-22T18:00:00+00:00",
        "input_count": 1,
        "mature_count": mature_count,
        "waiting_horizon_count": 1 if status == "WAITING_HORIZON" else 0,
        "ineligible_count": 1 if status == "INELIGIBLE" else 0,
        "items": [{
            "queue_position": 1,
            "player_id": "p1",
            "card_id": "c1",
            "decision_as_of": packet["as_of"],
            "status": status,
            "expected_export_filename": "01-player-one-forward.csv",
            "packet": packet,
            "entry_collection": _entry(),
        }],
    }


def test_manifest_run_grades_every_mature_item(tmp_path):
    _write_export(tmp_path, "01-player-one-forward.csv")
    result = run_authoritative_outcome_manifest(
        _manifest(), assets={"c1": _asset()}, export_dir=tmp_path
    )
    assert result["schema"] == "opportunity-authoritative-outcome-run.v1"
    assert result["mature_count"] == 1
    assert result["batch"]["graded_count"] == 1
    assert result["complete"] is True


def test_manifest_run_does_not_grade_waiting_horizon_items(tmp_path):
    result = run_authoritative_outcome_manifest(
        _manifest(status="WAITING_HORIZON", mature_count=0),
        assets={"c1": _asset()},
        export_dir=tmp_path,
    )
    assert result["mature_count"] == 0
    assert result["waiting_horizon_count"] == 1
    assert result["batch"]["input_count"] == 0
    assert result["complete"] is True


def test_manifest_run_keeps_missing_export_as_explicit_failure(tmp_path):
    result = run_authoritative_outcome_manifest(
        _manifest(), assets={"c1": _asset()}, export_dir=tmp_path
    )
    assert result["batch"]["failed_count"] == 1
    assert result["batch"]["results"][0]["status"] == "FAILED"
    assert result["complete"] is False


def test_manifest_run_fails_closed_on_mature_count_drift(tmp_path):
    with pytest.raises(ValueError, match="mature_count"):
        run_authoritative_outcome_manifest(
            _manifest(mature_count=0), assets={"c1": _asset()}, export_dir=tmp_path
        )
