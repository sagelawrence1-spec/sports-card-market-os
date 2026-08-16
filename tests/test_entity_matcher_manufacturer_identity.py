import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from entity_matcher import SportsCardEntityMatcher

M=SportsCardEntityMatcher()


def _asset(manufacturer="Topps"):
    return {
        "year": 2024,
        "manufacturer": manufacturer,
        "set_name": "Chrome",
        "player": "Shohei Ohtani",
        "card_number": "1",
        "parallel": "Base",
        "autograph": 0,
        "grade_company": "PSA",
        "grade": 10,
        "serial_number": "",
    }


def test_target_rejects_explicit_conflicting_manufacturer():
    decision=M.match(_asset(), "2024 Panini Chrome Shohei Ohtani #1 PSA 10")
    assert not decision.accepted
    assert decision.reason == "wrong_manufacturer"
    assert decision.diagnostics["conflicting_manufacturer_markers"] == ["panini"]


def test_target_without_manufacturer_evidence_goes_to_review():
    decision=M.match(_asset(), "2024 Chrome Shohei Ohtani #1 PSA 10")
    assert not decision.accepted
    assert decision.reason == "manual_review"
    assert decision.diagnostics["review_reason"] == "manufacturer_not_confirmed"


def test_matching_manufacturer_is_accepted():
    decision=M.match(_asset(), "2024 Topps Chrome Shohei Ohtani #1 PSA 10")
    assert decision.accepted
    assert decision.reason == "accepted"


def test_multiword_upper_deck_identity_is_confirmed():
    asset=_asset("Upper Deck")
    asset["set_name"]="Series 1"
    decision=M.match(asset, "2024 Upper Deck Series 1 Shohei Ohtani #1 PSA 10")
    assert decision.accepted
