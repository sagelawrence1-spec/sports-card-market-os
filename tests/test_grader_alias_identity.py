from entity_matcher import SportsCardEntityMatcher


M = SportsCardEntityMatcher()


def _asset(grade_company: str):
    return {
        "year": 2023,
        "manufacturer": "Topps",
        "set_name": "Chrome",
        "player": "Corbin Carroll",
        "card_number": "95",
        "parallel": "Base",
        "autograph": 0,
        "grade_company": grade_company,
        "grade": 9,
        "serial_number": "",
    }


def test_bgs_target_accepts_beckett_labeled_comp():
    decision = M.match(
        _asset("BGS"),
        "2023 Topps Chrome Corbin Carroll #95 Beckett 9",
    )
    assert decision.accepted
    assert decision.diagnostics["target_grader"] == "bgs"
    assert decision.diagnostics["observed_graders"] == ["bgs"]


def test_beckett_target_accepts_bgs_labeled_comp():
    decision = M.match(
        _asset("Beckett"),
        "2023 Topps Chrome Corbin Carroll #95 BGS 9",
    )
    assert decision.accepted
    assert decision.diagnostics["target_grader"] == "bgs"


def test_bgs_target_still_rejects_psa_comp():
    decision = M.match(
        _asset("BGS"),
        "2023 Topps Chrome Corbin Carroll #95 PSA 9",
    )
    assert not decision.accepted
    assert decision.reason == "wrong_grading_company"
    assert decision.diagnostics["other_grader"] == ["psa"]


def test_raw_target_rejects_beckett_labeled_comp():
    asset = _asset("")
    asset["grade"] = ""
    decision = M.match(
        asset,
        "2023 Topps Chrome Corbin Carroll #95 Beckett 9",
    )
    assert not decision.accepted
    assert decision.reason == "raw_vs_graded_mismatch"
    assert decision.diagnostics["unexpected_grader"] == ["bgs"]
