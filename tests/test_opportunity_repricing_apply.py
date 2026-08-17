import io
import json
from contextlib import redirect_stderr

import pytest

from opportunity_repricing_apply import apply_repricing_collection, main


def _observation():
    return {
        "player_id": "player-1",
        "player": "Player One",
        "sport": "baseball",
        "signal_kind": "CALL_UP",
        "signal_description": "Player One was promoted to MLB.",
        "observed_at": "2026-08-10T12:00:00+00:00",
        "headline": "Player One call-up creates a new hobby catalyst",
        "why_now": "The roster move creates immediate attention before pricing is proven.",
        "thesis": "If attention outruns card repricing, the first Bowman remains an entry expression.",
        "falsification": ["Role disappears", "Market reprices beyond the chase threshold"],
        "source_urls": ["https://example.com/player-one-call-up"],
        "factors": {
            "situation_change": 90,
            "narrative_potential": 90,
            "collectibility": 90,
            "hobby_lag": 90,
            "attention_velocity": 90,
            "evidence_maturity": 90,
            "upside_asymmetry": 90,
        },
        "cards": [{"card_id": "card-10", "label": "2026 Bowman Chrome Player One #10"}],
    }


def _collection(*, verified=True, repricing_pct=8.0, blocker=None):
    return {
        "schema": "opportunity-repricing-collection.v1",
        "player_id": "player-1",
        "card_id": "card-10",
        "verification": {
            "schema": "opportunity-repricing.v1",
            "verified": verified,
            "blocking_reason": blocker,
            "pre_count": 3,
            "post_count": 3 if verified else 1,
            "pre_median": 100.0 if verified else None,
            "post_median": 108.0 if verified else None,
            "repricing_pct": repricing_pct if verified else None,
            "evidence_ids": ["EBAY_PRODUCT_RESEARCH:1", "EBAY_PRODUCT_RESEARCH:2"],
            "catalyst_at": "2026-08-10T12:00:00+00:00",
            "as_of": "2026-08-18T10:00:00+00:00",
        },
    }


def test_verified_collection_upgrades_watch_to_engine_capital_decision():
    artifact = apply_repricing_collection(_observation(), _collection())
    assert artifact["schema"] == "opportunity-radar-repricing-update.v1"
    assert artifact["market_price_verified"] is True
    assert artifact["market_repricing_pct"] == 8.0
    assert artifact["decision"] == "START_POSITION"
    assert artifact["stage"] == "ENTRY"
    assert artifact["verification_blocking_reason"] is None


def test_large_verified_repricing_becomes_do_not_chase():
    artifact = apply_repricing_collection(_observation(), _collection(repricing_pct=40.0))
    assert artifact["decision"] == "DO_NOT_CHASE"
    assert artifact["engine_action"] == "DO_NOT_CHASE"


def test_unverified_collection_stays_non_actionable_and_preserves_blocker():
    artifact = apply_repricing_collection(
        _observation(),
        _collection(verified=False, blocker="insufficient_post_catalyst_comps"),
    )
    assert artifact["market_price_verified"] is False
    assert artifact["decision"] == "WATCH_FOR_COMPS"
    assert artifact["verification_blocking_reason"] == "insufficient_post_catalyst_comps"


@pytest.mark.parametrize("field,value,error", [
    ("player_id", "other-player", "player_id must match"),
    ("card_id", "other-card", "card_id must be an observation card expression"),
])
def test_collection_identity_must_bind_to_observation(field, value, error):
    collection = _collection()
    collection[field] = value
    with pytest.raises(ValueError, match=error):
        apply_repricing_collection(_observation(), collection)


def test_collection_catalyst_must_match_original_observation():
    collection = _collection()
    collection["verification"]["catalyst_at"] = "2026-08-11T12:00:00+00:00"
    with pytest.raises(ValueError, match="catalyst_at must match"):
        apply_repricing_collection(_observation(), collection)


def test_cli_emits_durable_decision_update(tmp_path):
    observation_path = tmp_path / "observation.json"
    collection_path = tmp_path / "collection.json"
    output_path = tmp_path / "update.json"
    observation_path.write_text(json.dumps(_observation()), encoding="utf-8")
    collection_path.write_text(json.dumps(_collection()), encoding="utf-8")

    assert main([
        "--observation", str(observation_path),
        "--collection", str(collection_path),
        "--output", str(output_path),
    ]) == 0
    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert artifact["decision"] == "START_POSITION"
    assert artifact["pricing_evidence_ids"]


def test_cli_fails_closed_on_non_object_collection(tmp_path):
    observation_path = tmp_path / "observation.json"
    collection_path = tmp_path / "collection.json"
    observation_path.write_text(json.dumps(_observation()), encoding="utf-8")
    collection_path.write_text("[]", encoding="utf-8")

    error = io.StringIO()
    with redirect_stderr(error):
        assert main(["--observation", str(observation_path), "--collection", str(collection_path)]) == 2
    assert "must be objects" in error.getvalue()
