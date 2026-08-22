import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from entity_matcher import SportsCardEntityMatcher


M = SportsCardEntityMatcher()


def _base_asset():
    return {
        "year": 2024,
        "manufacturer": "Panini",
        "set_name": "Prizm",
        "player": "Victor Wembanyama",
        "card_number": "136",
        "parallel": "Base",
        "autograph": 0,
        "grade_company": "PSA",
        "grade": 10,
        "serial_number": "",
    }


def test_base_target_rejects_checkerboard_parallel():
    decision = M.match(
        _base_asset(),
        "2024 Panini Prizm Victor Wembanyama #136 Checkerboard PSA 10",
    )
    assert not decision.accepted
    assert decision.reason == "unexpected_parallel"
    assert "checkerboard" in decision.diagnostics["unexpected_parallel"]


def test_base_target_rejects_cracked_ice_parallel():
    decision = M.match(
        _base_asset(),
        "2024 Panini Prizm Victor Wembanyama #136 Cracked Ice PSA 10",
    )
    assert not decision.accepted
    assert decision.reason == "unexpected_parallel"
    assert {"cracked", "ice"}.issubset(decision.diagnostics["unexpected_parallel"])


def test_base_target_rejects_green_pulsar_parallel_without_treating_green_alone_as_parallel():
    pulsar = M.match(
        _base_asset(),
        "2024 Panini Prizm Victor Wembanyama #136 Green Pulsar PSA 10",
    )
    assert not pulsar.accepted
    assert pulsar.reason == "unexpected_parallel"
    assert {"green", "pulsar"}.issubset(pulsar.diagnostics["unexpected_parallel"])

    team_color_only = M.match(
        _base_asset(),
        "2024 Panini Prizm Victor Wembanyama #136 San Antonio Green Jersey PSA 10",
    )
    assert team_color_only.accepted


def test_named_hyper_target_requires_hyper_and_accepts_exact_parallel():
    asset = {**_base_asset(), "parallel": "Hyper"}

    missing = M.match(
        asset,
        "2024 Panini Prizm Victor Wembanyama #136 PSA 10",
    )
    assert not missing.accepted
    assert missing.reason == "manual_review"
    assert missing.diagnostics["review_reason"] == "parallel_not_confirmed"

    exact = M.match(
        asset,
        "2024 Panini Prizm Victor Wembanyama #136 Hyper PSA 10",
    )
    assert exact.accepted
