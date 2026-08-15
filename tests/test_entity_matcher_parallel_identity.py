import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from entity_matcher import SportsCardEntityMatcher


M=SportsCardEntityMatcher()


def _asset(parallel="Gold Refractor"):
    return {
        "year":2024,
        "manufacturer":"Topps",
        "set_name":"Chrome",
        "player":"Shohei Ohtani",
        "card_number":"10",
        "parallel":parallel,
        "autograph":0,
        "grade_company":"PSA",
        "grade":10,
        "serial_number":"",
    }


def test_wrong_color_refractor_cannot_match_target_parallel():
    decision=M.match(_asset("Gold Refractor"),"2024 Topps Chrome Shohei Ohtani #10 Red Refractor PSA 10")
    assert not decision.accepted
    assert decision.reason == "wrong_parallel"
    assert "red" in decision.diagnostics["conflicting_parallel_markers"]


def test_named_parallel_requires_confirmation():
    decision=M.match(_asset("Gold Refractor"),"2024 Topps Chrome Shohei Ohtani #10 Refractor PSA 10")
    assert not decision.accepted
    assert decision.reason == "manual_review"
    assert decision.diagnostics["review_reason"] == "parallel_not_confirmed"


def test_compound_parallel_requires_all_identity_markers():
    decision=M.match(_asset("Gold Wave Refractor"),"2024 Topps Chrome Shohei Ohtani #10 Gold Refractor PSA 10")
    assert not decision.accepted
    assert decision.reason == "manual_review"
    assert decision.diagnostics["target_parallel_markers"] == ["gold","wave"]


def test_matching_named_parallel_accepts():
    decision=M.match(_asset("Gold Refractor"),"2024 Topps Chrome Shohei Ohtani #10 Gold Refractor PSA 10")
    assert decision.accepted
    assert decision.reason == "accepted"


def test_generic_refractor_still_accepts_when_confirmed():
    decision=M.match(_asset("Refractor"),"2024 Topps Chrome Shohei Ohtani #10 Refractor PSA 10")
    assert decision.accepted
    assert decision.reason == "accepted"


def test_base_target_rejects_sapphire_listing():
    decision=M.match(_asset("Base"),"2024 Topps Chrome Shohei Ohtani #10 Sapphire PSA 10")
    assert not decision.accepted
    assert decision.reason == "unexpected_parallel"
    assert decision.diagnostics["unexpected_parallel"] == ["sapphire"]


def test_base_target_rejects_wave_listing():
    decision=M.match(_asset("Base"),"2024 Topps Chrome Shohei Ohtani #10 Wave PSA 10")
    assert not decision.accepted
    assert decision.reason == "unexpected_parallel"
    assert decision.diagnostics["unexpected_parallel"] == ["wave"]


def test_base_target_rejects_atomic_listing():
    decision=M.match(_asset("Base"),"2024 Topps Chrome Shohei Ohtani #10 Atomic PSA 10")
    assert not decision.accepted
    assert decision.reason == "unexpected_parallel"
    assert decision.diagnostics["unexpected_parallel"] == ["atomic"]


def test_base_target_rejects_generic_refractor_listing():
    decision=M.match(_asset("Base"),"2024 Topps Chrome Shohei Ohtani #10 Refractor PSA 10")
    assert not decision.accepted
    assert decision.reason == "unexpected_parallel"
    assert decision.diagnostics["unexpected_parallel"] == ["refractor"]


def test_base_target_still_accepts_plain_base_listing():
    decision=M.match(_asset("Base"),"2024 Topps Chrome Shohei Ohtani #10 PSA 10")
    assert decision.accepted
    assert decision.reason == "accepted"
