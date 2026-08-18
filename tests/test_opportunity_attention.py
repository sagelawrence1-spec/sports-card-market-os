import pytest

from opportunity_attention import build_attention_brief


def _scan() -> dict:
    return {
        "schema": "opportunity-radar-scan.v1",
        "generated_at": "2026-08-17T15:00:00+00:00",
        "candidates": [
            {
                "rank": 1,
                "player_id": "p1",
                "player": "Prospect One",
                "stage": "ENTRY",
                "decision": "START_POSITION",
                "blocking_reason": None,
                "observed_at": "2026-08-17T13:45:00+00:00",
                "observation_to_scan_lag_minutes": 75.0,
                "headline": "Promotion confirmed",
                "why_now": "Attention is moving before broader repricing.",
                "thesis": "Entry remains open after verified modest repricing.",
                "falsification": ["Role disappears"],
                "source_urls": ["https://example.com/source"],
                "cards": [{"card_id": "c1", "label": "2025 Bowman Chrome Auto"}],
            },
            {
                "rank": 2,
                "player_id": "p2",
                "player": "Prospect Two",
                "stage": "PRE_CATALYST",
                "decision": "WATCH_FOR_COMPS",
                "blocking_reason": "authoritative_market_repricing_unverified",
                "observed_at": "2026-08-17T14:10:00+00:00",
                "observation_to_scan_lag_minutes": 50.0,
                "headline": "Call-up watch",
                "why_now": "Club comments indicate promotion risk.",
                "thesis": "Attention may move before the transaction.",
                "falsification": ["Player remains in minors"],
                "source_urls": ["https://example.com/source-2"],
                "cards": [{"card_id": "c2", "label": "2025 Bowman Chrome Prospect"}],
            },
        ],
    }


def _delta() -> dict:
    return {
        "schema": "opportunity-radar-delta.v1",
        "previous_generated_at": "2026-08-17T14:00:00+00:00",
        "current_generated_at": "2026-08-17T15:00:00+00:00",
        "movements": [
            {
                "player_id": "p1",
                "player": "Prospect One",
                "changes": ["REPRICING_VERIFIED", "DECISION_CHANGED"],
                "became_actionable": True,
                "needs_attention": True,
            },
            {
                "player_id": "p2",
                "player": "Prospect Two",
                "changes": ["UNCHANGED"],
                "became_actionable": False,
                "needs_attention": False,
            },
            {
                "player_id": "p3",
                "player": "Prospect Three",
                "changes": ["DROPPED"],
                "became_actionable": False,
                "needs_attention": True,
            },
        ],
    }


def test_attention_brief_surfaces_actionable_and_dropped_only():
    brief = build_attention_brief(_scan(), _delta())

    assert brief["schema"] == "opportunity-radar-attention.v1"
    assert brief["summary"] == {
        "attention_count": 2,
        "became_actionable_count": 1,
        "dropped_count": 1,
        "waiting_for_comps_count": 0,
        "under_6h_discovery_count": 1,
        "same_day_discovery_count": 0,
        "over_24h_discovery_count": 0,
    }
    assert [item["player_id"] for item in brief["items"]] == ["p1", "p3"]
    assert brief["items"][0]["decision"] == "START_POSITION"
    assert brief["items"][0]["observed_at"] == "2026-08-17T13:45:00+00:00"
    assert brief["items"][0]["observation_to_scan_lag_minutes"] == 75.0
    assert brief["items"][0]["discovery_age_bucket"] == "UNDER_6H"
    assert brief["items"][0]["cards"][0]["card_id"] == "c1"
    assert brief["items"][1]["status"] == "DROPPED"
    assert brief["items"][1]["observed_at"] is None
    assert brief["items"][1]["discovery_age_bucket"] == "UNKNOWN"


def test_attention_brief_reports_late_discovery_without_changing_decision():
    scan = _scan()
    scan["candidates"][0]["observation_to_scan_lag_minutes"] = 1600.0
    brief = build_attention_brief(scan, _delta())

    assert brief["items"][0]["decision"] == "START_POSITION"
    assert brief["items"][0]["discovery_age_bucket"] == "OVER_24H"
    assert brief["summary"]["over_24h_discovery_count"] == 1


def test_attention_brief_rejects_invalid_discovery_latency():
    scan = _scan()
    scan["candidates"][0]["observation_to_scan_lag_minutes"] = -1
    with pytest.raises(ValueError, match="non-negative number"):
        build_attention_brief(scan, _delta())


def test_attention_brief_rejects_misaligned_delta():
    delta = _delta()
    delta["current_generated_at"] = "2026-08-17T16:00:00+00:00"
    with pytest.raises(ValueError, match="must match scan generated_at"):
        build_attention_brief(_scan(), delta)


def test_attention_brief_requires_current_candidate_unless_dropped():
    delta = _delta()
    delta["movements"][2]["changes"] = ["DECISION_CHANGED"]
    with pytest.raises(ValueError, match="missing current candidate"):
        build_attention_brief(_scan(), delta)
