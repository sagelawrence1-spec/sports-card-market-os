import json
from pathlib import Path

import pytest

from opportunity_radar import scan_live_observations
from opportunity_report import build_radar_scan_artifact


FIXTURE = Path(__file__).parents[1] / "fixtures" / "opportunities" / "2026-08-17-live-radar-batch.json"


def test_live_radar_batch_builds_reviewable_scan_artifact():
    report = scan_live_observations(json.loads(FIXTURE.read_text()))
    artifact = build_radar_scan_artifact(report, generated_at="2026-08-17T07:05:00+00:00")

    assert artifact["schema"] == "opportunity-radar-scan.v1"
    assert artifact["source_schema"] == "opportunity-radar-batch.v1"
    assert artifact["generated_at"] == "2026-08-17T07:05:00+00:00"
    assert artifact["summary"] == {
        "input_count": 4,
        "candidate_count": 4,
        "actionable_count": 0,
        "duplicate_count": 0,
        "failure_count": 0,
        "waiting_for_comps_count": 4,
        "observed_at_count": 4,
        "missing_observed_at_count": 0,
        "median_observation_to_scan_lag_minutes": 6920.0,
        "max_observation_to_scan_lag_minutes": 19145.0,
    }
    assert [row["rank"] for row in artifact["candidates"]] == [1, 2, 3, 4]
    assert all(row["decision"] == "WATCH_FOR_COMPS" for row in artifact["candidates"])
    assert all(row["blocking_reason"] == "authoritative_market_repricing_unverified" for row in artifact["candidates"])
    assert all(row["observed_at"] for row in artifact["candidates"])
    assert all(row["observation_to_scan_lag_minutes"] is not None for row in artifact["candidates"])
    assert all(row["source_urls"] for row in artifact["candidates"])
    assert all(row["cards"] for row in artifact["candidates"])


def test_scan_artifact_preserves_ranked_card_and_thesis_evidence():
    payloads = json.loads(FIXTURE.read_text())
    report = scan_live_observations(payloads)
    artifact = build_radar_scan_artifact(report, generated_at="2026-08-17T07:05:00Z")
    by_player = {row["player_id"]: row for row in artifact["candidates"]}
    source_by_player = {row["player_id"]: row for row in payloads}

    baez = by_player["mlb-joshua-baez"]
    assert baez["stage"] == "ACCELERATION"
    assert baez["market_price_verified"] is False
    assert baez["observed_at"] == source_by_player["mlb-joshua-baez"]["observed_at"]
    assert baez["observation_to_scan_lag_minutes"] == 455.0
    assert baez["falsification"]
    assert baez["cards"][0]["card_id"] == "2022-bowman-chrome-prospects-bcp-112-joshua-baez"
    assert any("reuters.com" in url for url in baez["source_urls"])


def test_scan_artifact_rejects_naive_generated_timestamp():
    report = scan_live_observations([])
    with pytest.raises(ValueError, match="timezone-aware"):
        build_radar_scan_artifact(report, generated_at="2026-08-17T07:05:00")


def test_scan_artifact_rejects_future_observation():
    report = scan_live_observations(json.loads(FIXTURE.read_text()))
    with pytest.raises(ValueError, match="observed_at cannot be after generated_at"):
        build_radar_scan_artifact(report, generated_at="2026-08-16T23:40:00Z")


def test_scan_artifact_rejects_unknown_source_schema():
    report = scan_live_observations([])
    tampered = type(report)(
        schema="opportunity-radar-batch.v999",
        candidates=report.candidates,
        failures=report.failures,
        input_count=report.input_count,
        duplicate_count=report.duplicate_count,
    )
    with pytest.raises(ValueError, match="unsupported Radar batch schema"):
        build_radar_scan_artifact(tampered, generated_at="2026-08-17T07:05:00Z")
