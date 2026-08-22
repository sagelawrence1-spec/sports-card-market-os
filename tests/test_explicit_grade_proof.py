from entity_matcher import SportsCardEntityMatcher


M = SportsCardEntityMatcher()


def _asset(grade_company="PSA", grade=10):
    return {
        "year": 2023,
        "manufacturer": "Panini",
        "set_name": "Prizm",
        "player": "Victor Wembanyama",
        "card_number": "136",
        "parallel": "Silver",
        "autograph": 0,
        "grade_company": grade_company,
        "grade": grade,
        "serial_number": "",
    }


def test_matching_grader_without_numeric_grade_requires_review():
    decision = M.match(
        _asset(),
        "2023 Panini Prizm Victor Wembanyama #136 Silver Prizm PSA Gem Mint",
    )
    assert not decision.accepted
    assert decision.reason == "manual_review"
    assert decision.diagnostics["review_reason"] == "grade_not_confirmed"
    assert decision.diagnostics["grade_exact"] == 0


def test_matching_grader_with_wrong_numeric_grade_is_rejected():
    decision = M.match(
        _asset(),
        "2023 Panini Prizm Victor Wembanyama #136 Silver Prizm PSA 9",
    )
    assert not decision.accepted
    assert decision.reason == "wrong_grade"
    assert decision.diagnostics["explicit_grades"] == ["9"]


def test_integer_grade_does_not_prefix_match_decimal_grade():
    decision = M.match(
        _asset(),
        "2023 Panini Prizm Victor Wembanyama #136 Silver Prizm PSA 10.5",
    )
    assert not decision.accepted
    assert decision.reason == "wrong_grade"
    assert decision.diagnostics["grade_exact"] == 0
    assert decision.diagnostics["explicit_grades"] == ["10.5"]


def test_exact_numeric_grade_remains_accepted():
    decision = M.match(
        _asset(),
        "2023 Panini Prizm Victor Wembanyama #136 Silver Prizm PSA 10 Gem Mint",
    )
    assert decision.accepted
    assert decision.reason == "accepted"
    assert decision.diagnostics["grade_exact"] == 1


def test_exact_decimal_grade_remains_accepted():
    decision = M.match(
        _asset("BGS", 9.5),
        "2023 Panini Prizm Victor Wembanyama #136 Silver Prizm Beckett 9.5",
    )
    assert decision.accepted
    assert decision.reason == "accepted"
    assert decision.diagnostics["grade_exact"] == 1


def test_beckett_alias_without_numeric_grade_requires_review():
    decision = M.match(
        _asset("BGS", 9),
        "2023 Panini Prizm Victor Wembanyama #136 Silver Prizm Beckett Slab",
    )
    assert not decision.accepted
    assert decision.reason == "manual_review"
    assert decision.diagnostics["review_reason"] == "grade_not_confirmed"
    assert decision.diagnostics["target_grader"] == "bgs"
