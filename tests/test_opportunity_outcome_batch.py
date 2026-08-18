import csv

from opportunity_outcome_batch import grade_authoritative_outcome_batch


def _packet(player_id, card_id):
    return {
        "schema": "opportunity-decision-packet.v1",
        "player_id": player_id,
        "card": {"card_id": card_id, "label": "2026 Topps Chrome Player One #10"},
        "catalyst_at": "2026-08-10T12:00:00+00:00",
        "as_of": "2026-08-18T10:00:00+00:00",
        "decision": "START_POSITION",
        "actionable": True,
    }


def _entry(player_id, card_id):
    return {
        "schema": "opportunity-repricing-collection.v1",
        "player_id": player_id,
        "card_id": card_id,
        "verification": {
            "verified": True,
            "post_median": 100.0,
            "catalyst_at": "2026-08-10T12:00:00+00:00",
            "as_of": "2026-08-18T10:00:00+00:00",
        },
    }


def _asset(card_id):
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


def _write(tmp_path, name, prices):
    path = tmp_path / name
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Title", "Sold Price", "Sold Date", "Item ID", "Currency"])
        writer.writeheader()
        for idx, price in enumerate(prices, 1):
            writer.writerow({
                "Title": "2026 Topps Chrome Player One #10",
                "Sold Price": f"${price}",
                "Sold Date": f"2026-09-{17 + idx:02d}",
                "Item ID": str(idx),
                "Currency": "USD",
            })
    return str(path)


def _job(tmp_path, player_id="p1", card_id="c1", prices=(120, 130, 140)):
    return {
        "packet": _packet(player_id, card_id),
        "entry_collection": _entry(player_id, card_id),
        "asset": _asset(card_id),
        "csv_path": _write(tmp_path, f"{player_id}-{card_id}.csv", prices),
    }


def test_batch_grades_complete_authoritative_jobs(tmp_path):
    result = grade_authoritative_outcome_batch(
        [_job(tmp_path, "p1", "c1"), _job(tmp_path, "p2", "c2")],
        as_of="2026-09-22T18:00:00+00:00",
    )
    assert result["schema"] == "opportunity-authoritative-outcome-batch.v1"
    assert result["graded_count"] == 2
    assert result["blocked_count"] == 0
    assert result["failed_count"] == 0
    assert result["complete"] is True
    assert [row["status"] for row in result["results"]] == ["GRADED", "GRADED"]


def test_batch_keeps_thin_forward_evidence_explicit(tmp_path):
    result = grade_authoritative_outcome_batch(
        [_job(tmp_path, prices=(125,))],
        as_of="2026-09-22T18:00:00+00:00",
    )
    assert result["graded_count"] == 0
    assert result["blocked_count"] == 1
    assert result["complete"] is False
    assert result["results"][0]["proof"]["blocking_reason"] == "insufficient_forward_authoritative_comps"


def test_batch_rejects_duplicate_decision_identity(tmp_path):
    job = _job(tmp_path)
    result = grade_authoritative_outcome_batch([job, job], as_of="2026-09-22T18:00:00+00:00")
    assert result["graded_count"] == 1
    assert result["failed_count"] == 1
    assert result["complete"] is False
    assert result["results"][1]["reason"] == "duplicate_decision"


def test_batch_does_not_drop_missing_exports(tmp_path):
    job = _job(tmp_path)
    job["csv_path"] = str(tmp_path / "missing.csv")
    result = grade_authoritative_outcome_batch([job], as_of="2026-09-22T18:00:00+00:00")
    assert result["failed_count"] == 1
    assert result["complete"] is False
    assert result["results"][0]["status"] == "FAILED"
