from copy import deepcopy

import pytest

from opportunity_feed import process_opportunity_feed


def _observation() -> dict:
    return {
        "player_id": "player-1",
        "player": "Prospect One",
        "sport": "baseball",
        "signal_kind": "CALL_UP_WATCH",
        "signal_description": "Club is considering a near-term promotion.",
        "observed_at": "2026-08-17T10:00:00Z",
        "headline": "Promotion watch",
        "why_now": "Rotation opening plus public club comments.",
        "thesis": "Attention can move before the formal transaction.",
        "falsification": ["Player remains in the minors after the roster need resolves."],
        "source_urls": ["https://example.com/source"],
        "importance": 75,
        "novelty": 70,
        "market_impact": 65,
        "cards": [
            {
                "card_id": "card-1",
                "label": "2025 Bowman Chrome Prospect Auto",
                "priority": 1,
                "rationale": "Primary prospect autograph expression.",
            }
        ],
        "market_price_verified": False,
    }


def _feed() -> dict:
    return {
        "schema": "opportunity-radar-feed.v1",
        "publisher": "sports-card-market-os-test",
        "generated_at": "2026-08-17T11:00:00Z",
        "observations": [_observation()],
    }


def test_process_feed_emits_durable_scan_with_feed_provenance():
    artifact = process_opportunity_feed(_feed())

    assert artifact["schema"] == "opportunity-radar-scan.v1"
    assert artifact["feed"]["schema"] == "opportunity-radar-feed.v1"
    assert artifact["feed"]["publisher"] == "sports-card-market-os-test"
    assert artifact["feed"]["observation_count"] == 1
    assert artifact["summary"]["candidate_count"] == 1
    assert artifact["summary"]["actionable_count"] == 0
    assert artifact["candidates"][0]["decision"] == "WATCH_FOR_COMPS"
    assert artifact["candidates"][0]["stage"] == "PRE_CATALYST"


def test_feed_rejects_future_observation_leakage():
    feed = _feed()
    feed["observations"][0]["observed_at"] = "2026-08-17T12:00:00Z"

    with pytest.raises(ValueError, match="occurs after feed generated_at"):
        process_opportunity_feed(feed)


def test_feed_requires_timezone_aware_generated_at():
    feed = _feed()
    feed["generated_at"] = "2026-08-17T11:00:00"

    with pytest.raises(ValueError, match="generated_at must be timezone-aware"):
        process_opportunity_feed(feed)


def test_feed_rejects_missing_publisher():
    feed = _feed()
    feed["publisher"] = ""

    with pytest.raises(ValueError, match="publisher is required"):
        process_opportunity_feed(feed)


def test_feed_preserves_duplicate_accounting_from_radar():
    feed = _feed()
    feed["observations"].append(deepcopy(feed["observations"][0]))

    artifact = process_opportunity_feed(feed)

    assert artifact["feed"]["observation_count"] == 2
    assert artifact["summary"]["candidate_count"] == 1
    assert artifact["summary"]["duplicate_count"] == 1
