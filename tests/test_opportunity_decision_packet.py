import json

import pytest

from opportunity_decision_packet import build_opportunity_decision_packet, main


def _observation():
    return {
        "player_id": "player-1",
        "player": "Player One",
        "sport": "baseball",
        "signal_kind": "CALL_UP",
        "signal_description": "Player One was called up to the major-league roster.",
        "observed_at": "2026-08-10T12:00:00+00:00",
        "headline": "Player One call-up creates a hobby catalyst",
        "why_now": "Attention can outrun repricing after the promotion.",
        "thesis": "The first Bowman remains attractive if sold comps have not materially repriced.",
        "falsification": ["Role disappears", "Market reprices beyond chase threshold"],
        "source_urls": ["https://example.com/player-one"],
        "factors": {
            "situation_change": 90,
            "narrative_potential": 90,
            "collectibility": 90,
            "hobby_lag": 90,
            "attention_velocity": 90,
            "evidence_maturity": 90,
            "upside_asymmetry": 90,
        },
        "cards": [
            {"card_id": "card-10", "label": "2026 Bowman Chrome Player One #10"},
            {"card_id": "card-auto", "label": "2026 Bowman Chrome Auto Player One"},
        ],
    }


def _collection(*, verified=True, repricing_pct=8.0, blocker=None, as_of="2026-08-18T10:00:00+00:00"):
    return {
        "schema": "opportunity-repricing-collection.v1",
        "player_id": "player-1",
        "card_id": "card-10",
        "verification": {
            "schema": "opportunity-repricing.v1",
            "verified": verified,
            "blocking_reason": blocker,
            "repricing_pct": repricing_pct if verified else None,
            "evidence_ids": ["EBAY_PRODUCT_RESEARCH:1", "EBAY_PRODUCT_RESEARCH:2"],
            "catalyst_at": "2026-08-10T12:00:00+00:00",
            "as_of": as_of,
        },
    }


def test_packet_surfaces_actionable_call_with_evidence_and_falsification():
    packet = build_opportunity_decision_packet(_observation(), _collection())
    assert packet["schema"] == "opportunity-decision-packet.v1"
    assert packet["decision"] == "START_POSITION"
    assert packet["actionable"] is True
    assert packet["pricing"]["verified"] is True
    assert packet["pricing"]["repricing_pct"] == 8.0
    assert packet["card"]["card_id"] == "card-10"
    assert packet["falsification"]
    assert packet["source_urls"]
    assert packet["observed_at"] == "2026-08-10T12:00:00+00:00"
    assert packet["observation_to_decision_lag_minutes"] == 11400.0
    assert packet["decision_latency_bucket"] == "OVER_24H"


def test_packet_buckets_fast_decision_latency_without_changing_decision_logic():
    packet = build_opportunity_decision_packet(
        _observation(), _collection(as_of="2026-08-10T15:00:00+00:00")
    )
    assert packet["decision"] == "START_POSITION"
    assert packet["observation_to_decision_lag_minutes"] == 180.0
    assert packet["decision_latency_bucket"] == "UNDER_6H"


def test_packet_rejects_observation_after_decision_timestamp():
    with pytest.raises(ValueError, match="observed_at cannot be after decision as_of"):
        build_opportunity_decision_packet(
            _observation(), _collection(as_of="2026-08-10T11:59:00+00:00")
        )


def test_packet_preserves_non_actionable_pricing_blocker():
    packet = build_opportunity_decision_packet(
        _observation(),
        _collection(verified=False, blocker="insufficient_post_catalyst_comps"),
    )
    assert packet["decision"] == "WATCH_FOR_COMPS"
    assert packet["actionable"] is False
    assert packet["pricing"]["blocking_reason"] == "insufficient_post_catalyst_comps"


def test_packet_marks_large_repricing_as_not_actionable():
    packet = build_opportunity_decision_packet(_observation(), _collection(repricing_pct=40.0))
    assert packet["decision"] == "DO_NOT_CHASE"
    assert packet["actionable"] is False


def test_cli_writes_reviewable_packet(tmp_path):
    observation_path = tmp_path / "observation.json"
    collection_path = tmp_path / "collection.json"
    output_path = tmp_path / "packet.json"
    observation_path.write_text(json.dumps(_observation()), encoding="utf-8")
    collection_path.write_text(json.dumps(_collection()), encoding="utf-8")

    code = main([
        "--observation", str(observation_path),
        "--collection", str(collection_path),
        "--output", str(output_path),
    ])
    assert code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "opportunity-decision-packet.v1"
    assert payload["decision"] == "START_POSITION"
    assert payload["decision_latency_bucket"] == "OVER_24H"
