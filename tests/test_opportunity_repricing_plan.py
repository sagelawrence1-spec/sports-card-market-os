from opportunity_repricing_plan import build_repricing_plan


def _scan() -> dict:
    return {
        "schema": "opportunity-radar-scan.v1",
        "generated_at": "2026-08-17T17:00:00+00:00",
        "candidates": [
            {
                "rank": 1,
                "thesis_id": "thesis-1",
                "player_id": "mlb-player-1",
                "player": "Player One",
                "stage": "ENTRY",
                "decision": "WATCH_FOR_COMPS",
                "observed_at": "2026-08-16T12:00:00+00:00",
                "observation_to_scan_lag_minutes": 120.0,
                "cards": [
                    {"card_id": "card-auto", "label": "Chrome Auto", "priority": 2},
                    {"card_id": "card-base", "label": "Chrome Base", "priority": 1},
                ],
            }
        ],
    }


def test_plan_anchors_windows_to_catalyst_not_scan_time():
    plan = build_repricing_plan(_scan())
    assert plan["schema"] == "opportunity-repricing-plan.v1"
    assert plan["request_count"] == 2
    assert [row["card_id"] for row in plan["requests"]] == ["card-base", "card-auto"]
    request = plan["requests"][0]
    assert request["catalyst_at"] == "2026-08-16T12:00:00+00:00"
    assert request["pre_start"] == "2026-07-17T12:00:00+00:00"
    assert request["pre_end_exclusive"] == request["catalyst_at"]
    assert request["post_window_end"] == "2026-08-23T12:00:00+00:00"
    assert request["queryable_post_end"] == "2026-08-17T17:00:00+00:00"
    assert request["status"] == "COLLECTION_OPEN"
    assert request["source_type"] == "EBAY_PRODUCT_RESEARCH"
    assert request["collection_priority"] == "P0"
    assert plan["priority_counts"] == {"P0": 2, "P1": 0, "P2": 0}


def test_plan_marks_post_window_mature_without_extending_evidence_window():
    plan = build_repricing_plan(_scan(), as_of="2026-08-25T00:00:00+00:00")
    request = plan["requests"][0]
    assert request["status"] == "WINDOW_MATURE"
    assert request["queryable_post_end"] == "2026-08-23T12:00:00+00:00"
    assert plan["mature_count"] == 2
    assert plan["open_count"] == 0


def test_plan_prioritizes_fresh_early_stage_manual_comp_work():
    scan = _scan()
    scan["candidates"].append(
        {
            "rank": 2,
            "thesis_id": "thesis-2",
            "player_id": "mlb-player-2",
            "player": "Player Two",
            "stage": "ACCELERATION",
            "decision": "WATCH_FOR_COMPS",
            "observed_at": "2026-08-10T12:00:00+00:00",
            "observation_to_scan_lag_minutes": 7 * 24 * 60,
            "cards": [{"card_id": "older-card", "label": "Older Auto", "priority": 1}],
        }
    )
    plan = build_repricing_plan(scan)
    assert [row["player_id"] for row in plan["requests"]] == [
        "mlb-player-1",
        "mlb-player-1",
        "mlb-player-2",
    ]
    assert [row["collection_priority"] for row in plan["requests"]] == ["P0", "P0", "P1"]
    assert plan["priority_counts"] == {"P0": 2, "P1": 1, "P2": 0}


def test_plan_does_not_promote_already_actionable_candidate_to_collection_priority():
    scan = _scan()
    scan["candidates"][0]["decision"] = "START_POSITION"
    plan = build_repricing_plan(scan)
    assert {row["collection_priority"] for row in plan["requests"]} == {"P2"}
    assert plan["priority_counts"] == {"P0": 0, "P1": 0, "P2": 2}


def test_plan_rejects_missing_catalyst_time():
    scan = _scan()
    scan["candidates"][0]["observed_at"] = None
    try:
        build_repricing_plan(scan)
    except ValueError as exc:
        assert "requires observed_at" in str(exc)
    else:
        raise AssertionError("missing catalyst timestamp must fail closed")


def test_plan_rejects_as_of_before_catalyst():
    try:
        build_repricing_plan(_scan(), as_of="2026-08-16T11:59:59+00:00")
    except ValueError as exc:
        assert "cannot precede catalyst" in str(exc)
    else:
        raise AssertionError("future catalyst leakage must fail closed")


def test_plan_rejects_duplicate_card_request_identity():
    scan = _scan()
    scan["candidates"][0]["cards"].append({"card_id": "card-base", "label": "Duplicate", "priority": 3})
    try:
        build_repricing_plan(scan)
    except ValueError as exc:
        assert "duplicate repricing request identity" in str(exc)
    else:
        raise AssertionError("duplicate repricing requests must fail closed")
