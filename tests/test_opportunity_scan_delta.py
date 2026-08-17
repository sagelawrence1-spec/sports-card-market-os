import pytest

from opportunity_scan_delta import build_radar_scan_delta


def _scan(at, candidates):
    return {
        "schema": "opportunity-radar-scan.v1",
        "generated_at": at,
        "candidates": candidates,
    }


def _candidate(player_id, *, rank=1, stage="ENTRY", decision="WATCH_FOR_COMPS", verified=False, blocker="authoritative_market_repricing_unverified", thesis_id=None):
    return {
        "rank": rank,
        "thesis_id": thesis_id or f"thesis-{player_id}",
        "player_id": player_id,
        "player": player_id.title(),
        "stage": stage,
        "decision": decision,
        "blocking_reason": blocker,
        "market_price_verified": verified,
        "edge_conviction": 70.0,
        "evidence_confidence": 65.0,
    }


def test_delta_surfaces_new_actionable_candidate_first():
    previous = _scan("2026-08-17T07:00:00Z", [_candidate("alpha")])
    current = _scan(
        "2026-08-17T08:00:00Z",
        [
            _candidate("alpha", rank=2),
            _candidate("beta", rank=1, stage="ACCELERATION", decision="START_POSITION", verified=True, blocker=None),
        ],
    )

    artifact = build_radar_scan_delta(previous, current)

    assert artifact["schema"] == "opportunity-radar-delta.v1"
    assert artifact["summary"]["new_count"] == 1
    assert artifact["summary"]["became_actionable_count"] == 1
    assert artifact["movements"][0]["player_id"] == "beta"
    assert artifact["movements"][0]["changes"] == ["NEW"]
    assert artifact["movements"][0]["became_actionable"] is True


def test_delta_detects_repricing_and_decision_transition_without_joining_on_thesis_uuid():
    previous = _scan(
        "2026-08-17T07:00:00Z",
        [_candidate("alpha", thesis_id="old-thesis")],
    )
    current = _scan(
        "2026-08-17T08:00:00Z",
        [_candidate("alpha", decision="ADD", verified=True, blocker=None, thesis_id="new-thesis")],
    )

    row = build_radar_scan_delta(previous, current)["movements"][0]

    assert row["previous_thesis_id"] == "old-thesis"
    assert row["current_thesis_id"] == "new-thesis"
    assert "DECISION_CHANGED" in row["changes"]
    assert "REPRICING_VERIFIED" in row["changes"]
    assert "BLOCKER_CHANGED" in row["changes"]
    assert row["became_actionable"] is True


def test_delta_detects_stage_advance_and_dropped_candidate():
    previous = _scan(
        "2026-08-17T07:00:00Z",
        [_candidate("alpha", stage="ENTRY"), _candidate("gone", rank=2)],
    )
    current = _scan(
        "2026-08-17T08:00:00Z",
        [_candidate("alpha", stage="ACCELERATION")],
    )

    by_player = {row["player_id"]: row for row in build_radar_scan_delta(previous, current)["movements"]}
    assert "STAGE_ADVANCED" in by_player["alpha"]["changes"]
    assert by_player["gone"]["changes"] == ["DROPPED"]
    assert by_player["gone"]["needs_attention"] is True


def test_delta_marks_unchanged_candidate_without_attention():
    candidate = _candidate("alpha")
    previous = _scan("2026-08-17T07:00:00Z", [candidate])
    current = _scan("2026-08-17T08:00:00Z", [dict(candidate)])

    row = build_radar_scan_delta(previous, current)["movements"][0]
    assert row["changes"] == ["UNCHANGED"]
    assert row["needs_attention"] is False


def test_delta_rejects_non_chronological_scans():
    previous = _scan("2026-08-17T08:00:00Z", [])
    current = _scan("2026-08-17T08:00:00Z", [])
    with pytest.raises(ValueError, match="strictly later"):
        build_radar_scan_delta(previous, current)


def test_delta_rejects_duplicate_player_identity():
    previous = _scan("2026-08-17T07:00:00Z", [_candidate("alpha"), _candidate("alpha", rank=2)])
    current = _scan("2026-08-17T08:00:00Z", [])
    with pytest.raises(ValueError, match="duplicate player_id"):
        build_radar_scan_delta(previous, current)


def test_delta_rejects_unknown_scan_schema():
    previous = {"schema": "opportunity-radar-scan.v999", "generated_at": "2026-08-17T07:00:00Z", "candidates": []}
    current = _scan("2026-08-17T08:00:00Z", [])
    with pytest.raises(ValueError, match="unsupported previous scan schema"):
        build_radar_scan_delta(previous, current)
