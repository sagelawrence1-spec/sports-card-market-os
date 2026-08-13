import pytest

from portfolio_exposure import (
    CandidateExposure,
    ExposurePolicy,
    PositionExposure,
    apply_exposure_caps,
)


def _candidate(card_id="c1", **overrides):
    values = {
        "card_id": card_id,
        "player_id": "shohei-ohtani",
        "sport": "MLB",
        "set_family": "Topps Chrome",
        "thesis_id": "ohtani-long-term",
        "correlated_bucket": "modern-mlb-superstar",
    }
    values.update(overrides)
    return CandidateExposure(**values)


def _position(value, **overrides):
    candidate = _candidate(**overrides)
    return PositionExposure(
        card_id=f"held-{value}-{candidate.player_id}",
        market_value=value,
        player_id=candidate.player_id,
        sport=candidate.sport,
        set_family=candidate.set_family,
        thesis_id=candidate.thesis_id,
        correlated_bucket=candidate.correlated_bucket,
    )


def test_missing_exposure_metadata_fails_closed():
    rows = apply_exposure_caps(
        [{"card_id": "c1", "allocation": 500, "ready": True, "blockers": []}],
        {},
        portfolio_value=10_000,
    )
    assert rows[0]["exposure_adjusted_allocation"] == 0
    assert rows[0]["exposure_blockers"] == ["missing_exposure_metadata"]


def test_player_cap_reduces_allocation_to_remaining_headroom():
    policy = ExposurePolicy(
        max_player_pct=0.15,
        max_sport_pct=1.0,
        max_set_family_pct=1.0,
        max_single_thesis_pct=1.0,
        max_correlated_bucket_pct=1.0,
    )
    rows = apply_exposure_caps(
        [{"card_id": "c1", "allocation": 500, "ready": True, "blockers": []}],
        {"c1": _candidate()},
        portfolio_value=10_000,
        positions=[_position(1_300)],
        policy=policy,
    )
    assert rows[0]["exposure_adjusted_allocation"] == 200


def test_correlated_bucket_can_bind_before_player_cap():
    policy = ExposurePolicy(
        max_player_pct=0.50,
        max_sport_pct=0.50,
        max_set_family_pct=0.50,
        max_single_thesis_pct=0.50,
        max_correlated_bucket_pct=0.20,
    )
    held = _position(1_850, player_id="aaron-judge", thesis_id="judge-long-term")
    rows = apply_exposure_caps(
        [{"card_id": "c1", "allocation": 600, "ready": True, "blockers": []}],
        {"c1": _candidate()},
        portfolio_value=10_000,
        positions=[held],
        policy=policy,
    )
    assert rows[0]["exposure_adjusted_allocation"] == 150


def test_sequential_allocations_consume_shared_headroom():
    policy = ExposurePolicy(
        max_player_pct=0.20,
        max_sport_pct=0.30,
        max_set_family_pct=1.0,
        max_single_thesis_pct=1.0,
        max_correlated_bucket_pct=1.0,
    )
    allocations = [
        {"card_id": "a", "allocation": 2_000, "ready": True, "blockers": []},
        {"card_id": "b", "allocation": 2_000, "ready": True, "blockers": []},
    ]
    exposure = {
        "a": _candidate("a", player_id="player-a", thesis_id="a"),
        "b": _candidate("b", player_id="player-b", thesis_id="b"),
    }
    rows = apply_exposure_caps(
        allocations,
        exposure,
        portfolio_value=10_000,
        policy=policy,
    )
    assert rows[0]["exposure_adjusted_allocation"] == 2_000
    assert rows[1]["exposure_adjusted_allocation"] == 1_000


def test_upstream_rejected_candidate_never_gets_restored():
    rows = apply_exposure_caps(
        [{
            "card_id": "c1",
            "allocation": 0,
            "ready": False,
            "blockers": ["segment_sample_too_small"],
        }],
        {"c1": _candidate()},
        portfolio_value=10_000,
    )
    assert rows[0]["exposure_adjusted_allocation"] == 0
    assert "segment_sample_too_small" in rows[0]["exposure_blockers"]


def test_policy_rejects_invalid_caps():
    with pytest.raises(ValueError):
        ExposurePolicy(max_player_pct=0)
