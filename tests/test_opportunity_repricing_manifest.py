from __future__ import annotations

import json

from opportunity_repricing_manifest import build_collection_manifest
from opportunity_repricing_manifest_cli import main


def _plan() -> dict:
    return {
        "schema": "opportunity-repricing-plan.v1",
        "source_scan_generated_at": "2026-08-18T15:00:00+00:00",
        "as_of": "2026-08-18T15:00:00+00:00",
        "requests": [
            {
                "candidate_rank": 2,
                "collection_priority": "P1",
                "collection_priority_reason": "active opportunity waiting on authoritative comps",
                "player_id": "player-two",
                "player": "Player Two",
                "card_id": "card-two",
                "card_label": "Chrome Auto #2",
                "card_priority": 1,
                "stage": "ACCELERATION",
                "decision": "WATCH_FOR_COMPS",
                "source_type": "EBAY_PRODUCT_RESEARCH",
                "catalyst_at": "2026-08-17T12:00:00+00:00",
                "pre_start": "2026-07-18T12:00:00+00:00",
                "queryable_post_end": "2026-08-18T15:00:00+00:00",
                "status": "COLLECTION_OPEN",
            },
            {
                "candidate_rank": 1,
                "collection_priority": "P0",
                "collection_priority_reason": "fresh early-stage opportunity waiting on authoritative comps",
                "player_id": "player-one",
                "player": "Player One",
                "card_id": "card-one",
                "card_label": "Bowman Chrome Auto CPA-PO",
                "card_priority": 1,
                "stage": "ENTRY",
                "decision": "WATCH_FOR_COMPS",
                "source_type": "EBAY_PRODUCT_RESEARCH",
                "catalyst_at": "2026-08-18T10:00:00+00:00",
                "pre_start": "2026-07-19T10:00:00+00:00",
                "queryable_post_end": "2026-08-18T15:00:00+00:00",
                "status": "COLLECTION_OPEN",
            },
            {
                "candidate_rank": 3,
                "collection_priority": "P2",
                "collection_priority_reason": "lower-urgency repricing verification",
                "player_id": "player-three",
                "player": "Player Three",
                "card_id": "card-three",
                "card_label": "Base",
                "card_priority": 1,
                "stage": "ACCELERATION",
                "decision": "START_POSITION",
                "source_type": "EBAY_PRODUCT_RESEARCH",
                "catalyst_at": "2026-08-16T10:00:00+00:00",
                "pre_start": "2026-07-17T10:00:00+00:00",
                "queryable_post_end": "2026-08-18T15:00:00+00:00",
                "status": "COLLECTION_OPEN",
            },
        ],
    }


def test_manifest_prioritizes_p0_then_p1_and_excludes_p2_by_default():
    manifest = build_collection_manifest(_plan())
    assert manifest["schema"] == "opportunity-repricing-collection-manifest.v1"
    assert [item["player_id"] for item in manifest["items"]] == ["player-one", "player-two"]
    assert manifest["priority_counts"] == {"P0": 1, "P1": 1, "P2": 0}
    assert manifest["items"][0]["queue_position"] == 1
    assert manifest["items"][0]["expected_export_filename"].endswith(".csv")
    assert "complete result set" in manifest["items"][0]["collection_instruction"]


def test_manifest_can_include_p2_and_cap_work_queue():
    manifest = build_collection_manifest(_plan(), max_requests=2, include_p2=True)
    assert manifest["selected_request_count"] == 2
    assert manifest["remaining_request_count"] == 1
    assert [item["collection_priority"] for item in manifest["items"]] == ["P0", "P1"]


def test_manifest_rejects_non_authoritative_source():
    plan = _plan()
    plan["requests"][0]["source_type"] = "OTHER"
    try:
        build_collection_manifest(plan)
    except ValueError as exc:
        assert "authoritative eBay Product Research" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_manifest_rejects_duplicate_player_card_requests():
    plan = _plan()
    plan["requests"].append(dict(plan["requests"][0]))
    try:
        build_collection_manifest(plan, include_p2=True)
    except ValueError as exc:
        assert "duplicate player/card" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_manifest_cli_writes_json(tmp_path):
    plan_path = tmp_path / "plan.json"
    out_path = tmp_path / "manifest.json"
    plan_path.write_text(json.dumps(_plan()), encoding="utf-8")
    assert main(["--plan", str(plan_path), "-o", str(out_path)]) == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "opportunity-repricing-collection-manifest.v1"
    assert payload["selected_request_count"] == 2


def test_manifest_requires_positive_max_requests():
    try:
        build_collection_manifest(_plan(), max_requests=0)
    except ValueError as exc:
        assert "positive integer" in str(exc)
    else:
        raise AssertionError("expected ValueError")
