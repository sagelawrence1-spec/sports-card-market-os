import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from entity_matcher import SportsCardEntityMatcher


M=SportsCardEntityMatcher()


def _asset(set_name="Chrome"):
    return {
        "year":2024,
        "manufacturer":"Topps",
        "set_name":set_name,
        "player":"Shohei Ohtani",
        "card_number":"10",
        "parallel":"Base",
        "autograph":0,
        "grade_company":"PSA",
        "grade":10,
        "serial_number":"",
    }


def test_conflicting_bowman_family_cannot_match_topps_chrome_target():
    decision=M.match(_asset("Chrome"),"2024 Bowman Chrome Shohei Ohtani #10 PSA 10")
    assert not decision.accepted
    assert decision.reason == "wrong_set_family"
    assert decision.diagnostics["conflicting_set_markers"] == ["bowman"]


def test_distinctive_target_family_must_be_confirmed():
    decision=M.match(_asset("Bowman Chrome"),"2024 Topps Chrome Shohei Ohtani #10 PSA 10")
    assert not decision.accepted
    assert decision.reason == "set_family_not_confirmed"
    assert decision.diagnostics["target_set_markers"] == ["bowman"]


def test_matching_distinctive_family_still_accepts():
    decision=M.match(_asset("Bowman Chrome"),"2024 Bowman Chrome Shohei Ohtani #10 PSA 10")
    assert decision.accepted
    assert decision.reason == "accepted"


def test_panini_product_lines_do_not_cross_match():
    asset=_asset("Prizm")
    asset["manufacturer"]="Panini"
    decision=M.match(asset,"2024 Panini Select Shohei Ohtani #10 PSA 10")
    assert not decision.accepted
    assert decision.reason == "set_family_not_confirmed"
    assert decision.diagnostics["target_set_markers"] == ["prizm"]
    assert decision.diagnostics["title_set_markers"] == ["select"]


def test_generic_chrome_title_without_conflicting_family_is_not_over_rejected():
    decision=M.match(_asset("Chrome"),"2024 Topps Chrome Shohei Ohtani #10 PSA 10")
    assert decision.accepted


def test_topps_flagship_target_rejects_topps_chrome_listing():
    decision=M.match(_asset("Topps"),"2024 Topps Chrome Shohei Ohtani #10 PSA 10")
    assert not decision.accepted
    assert decision.reason == "wrong_set_family"
    assert decision.diagnostics["target_chrome"] == 0
    assert decision.diagnostics["title_chrome"] == 1


def test_topps_chrome_target_requires_chrome_evidence():
    decision=M.match(_asset("Topps Chrome"),"2024 Topps Shohei Ohtani #10 PSA 10")
    assert not decision.accepted
    assert decision.reason == "set_family_not_confirmed"
    assert decision.diagnostics["target_chrome"] == 1
    assert decision.diagnostics["title_chrome"] == 0


def test_bowman_chrome_target_rejects_bowman_paper_listing():
    decision=M.match(_asset("Bowman Chrome"),"2024 Bowman Shohei Ohtani #10 PSA 10")
    assert not decision.accepted
    assert decision.reason == "set_family_not_confirmed"
    assert decision.diagnostics["target_chrome"] == 1
    assert decision.diagnostics["title_chrome"] == 0


def test_bowman_paper_target_rejects_bowman_chrome_listing():
    decision=M.match(_asset("Bowman"),"2024 Bowman Chrome Shohei Ohtani #10 PSA 10")
    assert not decision.accepted
    assert decision.reason == "wrong_set_family"
    assert decision.diagnostics["target_chrome"] == 0
    assert decision.diagnostics["title_chrome"] == 1


def test_topps_now_target_requires_now_evidence():
    decision=M.match(_asset("Topps Now"),"2024 Topps Shohei Ohtani #10 PSA 10")
    assert not decision.accepted
    assert decision.reason == "set_family_not_confirmed"
    assert decision.diagnostics["target_set_markers"] == ["now"]


def test_topps_flagship_target_rejects_topps_now_listing():
    decision=M.match(_asset("Topps"),"2024 Topps Now Shohei Ohtani #10 PSA 10")
    assert not decision.accepted
    assert decision.reason == "wrong_set_family"
    assert decision.diagnostics["conflicting_set_markers"] == ["now"]


def test_matching_topps_now_family_still_accepts():
    decision=M.match(_asset("Topps Now"),"2024 Topps Now Shohei Ohtani #10 PSA 10")
    assert decision.accepted
    assert decision.reason == "accepted"


def test_topps_update_target_requires_update_evidence():
    decision=M.match(_asset("Topps Update"),"2024 Topps Shohei Ohtani #10 PSA 10")
    assert not decision.accepted
    assert decision.reason == "wrong_set_family"
    assert decision.diagnostics["target_update"] == 1
    assert decision.diagnostics["title_update"] == 0


def test_topps_flagship_target_rejects_topps_update_listing():
    decision=M.match(_asset("Topps"),"2024 Topps Update Shohei Ohtani #10 PSA 10")
    assert not decision.accepted
    assert decision.reason == "wrong_set_family"
    assert decision.diagnostics["target_update"] == 0
    assert decision.diagnostics["title_update"] == 1


def test_matching_topps_update_family_still_accepts():
    decision=M.match(_asset("Topps Update"),"2024 Topps Update Shohei Ohtani #10 PSA 10")
    assert decision.accepted
    assert decision.reason == "accepted"
