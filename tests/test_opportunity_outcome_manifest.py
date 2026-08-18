from opportunity_outcome_manifest import build_authoritative_outcome_manifest


def _packet(actionable=True, decision="START_POSITION", as_of="2026-08-18T10:00:00+00:00"):
    return {
        "schema": "opportunity-decision-packet.v1",
        "player_id": "p1",
        "player": "Player One",
        "card": {"card_id": "c1", "label": "2026 Topps Chrome Player One #10"},
        "catalyst_at": "2026-08-10T12:00:00+00:00",
        "as_of": as_of,
        "decision": decision,
        "actionable": actionable,
    }


def _entry():
    return {
        "schema": "opportunity-repricing-collection.v1",
        "player_id": "p1",
        "card_id": "c1",
        "verification": {"verified": True, "post_median": 100.0},
    }


def test_manifest_marks_mature_actionable_call_collection_ready():
    result = build_authoritative_outcome_manifest(
        [{"packet": _packet(), "entry_collection": _entry()}],
        as_of="2026-09-20T10:00:00+00:00",
    )
    assert result["schema"] == "opportunity-authoritative-outcome-manifest.v1"
    assert result["mature_count"] == 1
    assert result["collection_ready"] is True
    item = result["items"][0]
    assert item["status"] == "MATURE"
    assert item["horizon_end"] == "2026-09-17T10:00:00+00:00"
    assert item["expected_export_filename"].endswith("-forward.csv")
    assert item["packet"]["player_id"] == "p1"


def test_manifest_keeps_prehorizon_call_visible():
    result = build_authoritative_outcome_manifest(
        [{"packet": _packet(), "entry_collection": _entry()}],
        as_of="2026-09-01T10:00:00+00:00",
    )
    assert result["mature_count"] == 0
    assert result["waiting_horizon_count"] == 1
    assert result["collection_ready"] is False
    assert result["items"][0]["status"] == "WAITING_HORIZON"


def test_manifest_keeps_nonactionable_decision_explicit():
    result = build_authoritative_outcome_manifest(
        [{"packet": _packet(actionable=False, decision="WATCH_FOR_COMPS"), "entry_collection": _entry()}],
        as_of="2026-09-20T10:00:00+00:00",
    )
    assert result["ineligible_count"] == 1
    assert result["items"][0]["status"] == "INELIGIBLE"


def test_manifest_rejects_duplicate_decision_identity():
    job = {"packet": _packet(), "entry_collection": _entry()}
    try:
        build_authoritative_outcome_manifest([job, job], as_of="2026-09-20T10:00:00+00:00")
    except ValueError as exc:
        assert str(exc) == "duplicate decision identity"
    else:
        raise AssertionError("expected duplicate decision identity to fail")
