import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from entity_matcher import SportsCardEntityMatcher


M=SportsCardEntityMatcher()


def _asset(card_number="10", grade=10):
    return {
        "year":2024,
        "manufacturer":"Topps",
        "set_name":"Chrome",
        "player":"Shohei Ohtani",
        "card_number":card_number,
        "parallel":"Base",
        "autograph":0,
        "grade_company":"PSA",
        "grade":grade,
        "serial_number":"",
    }


def test_psa_grade_does_not_masquerade_as_numeric_card_number():
    decision=M.match(_asset(),"2024 Topps Chrome Shohei Ohtani PSA 10")
    assert not decision.accepted
    assert decision.reason == "manual_review"
    assert decision.diagnostics["card_number_match"] == 0
    assert decision.diagnostics["review_reason"] == "card_number_not_confirmed"


def test_missing_card_number_cannot_auto_accept_even_with_strong_other_identity():
    decision=M.match(_asset(card_number="25"),"2024 Topps Chrome Shohei Ohtani PSA 10")
    assert not decision.accepted
    assert decision.reason == "manual_review"
    assert decision.diagnostics["review_reason"] == "card_number_not_confirmed"


def test_explicit_numeric_card_number_still_auto_accepts():
    decision=M.match(_asset(),"2024 Topps Chrome Shohei Ohtani #10 PSA 10")
    assert decision.accepted
    assert decision.diagnostics["card_number_match"] == 1


def test_card_marker_is_valid_numeric_card_number_evidence():
    decision=M.match(_asset(card_number="136"),"2024 Topps Chrome Shohei Ohtani Card 136 PSA 10")
    assert decision.accepted
    assert decision.diagnostics["card_number_match"] == 1


def test_alphanumeric_catalog_number_can_match_standalone():
    decision=M.match(_asset(card_number="HMT1"),"2024 Topps Chrome Shohei Ohtani HMT1 PSA 10")
    assert decision.accepted
    assert decision.diagnostics["card_number_match"] == 1


def test_explicit_wrong_card_number_fails_closed():
    decision=M.match(_asset(card_number="10"),"2024 Topps Chrome Shohei Ohtani #11 PSA 10")
    assert not decision.accepted
    assert decision.reason == "wrong_card_number"
