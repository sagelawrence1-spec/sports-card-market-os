from entity_matcher import SportsCardEntityMatcher


MATCHER = SportsCardEntityMatcher()


def _asset(set_name):
    return {
        "year": 2024,
        "manufacturer": "Topps",
        "set_name": set_name,
        "player": "Caleb Bonemer",
        "card_number": "BDC-17",
        "parallel": "Base",
        "autograph": 0,
        "grade_company": "PSA",
        "grade": 10,
        "serial_number": "",
    }


def test_standard_bowman_chrome_rejects_bowman_draft_chrome_listing():
    decision = MATCHER.match(
        _asset("Bowman Chrome"),
        "2024 Bowman Draft Chrome Caleb Bonemer BDC-17 PSA 10",
    )
    assert decision.accepted is False
    assert decision.reason == "wrong_set_family"
    assert decision.diagnostics["target_draft"] == 0
    assert decision.diagnostics["title_draft"] == 1


def test_bowman_draft_chrome_rejects_standard_bowman_chrome_listing():
    decision = MATCHER.match(
        _asset("Bowman Draft Chrome"),
        "2024 Bowman Chrome Caleb Bonemer BDC-17 PSA 10",
    )
    assert decision.accepted is False
    assert decision.reason == "wrong_set_family"
    assert decision.diagnostics["target_draft"] == 1
    assert decision.diagnostics["title_draft"] == 0


def test_matching_bowman_draft_chrome_listing_accepts():
    decision = MATCHER.match(
        _asset("Bowman Draft Chrome"),
        "2024 Bowman Draft Chrome Caleb Bonemer BDC-17 PSA 10",
    )
    assert decision.accepted is True
    assert decision.reason == "accepted"
