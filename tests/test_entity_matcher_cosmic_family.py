from entity_matcher import SportsCardEntityMatcher


MATCHER = SportsCardEntityMatcher()


def _asset(set_name):
    return {
        "year": 2025,
        "manufacturer": "Topps",
        "set_name": set_name,
        "player": "Shohei Ohtani",
        "card_number": "14",
        "parallel": "Base",
        "autograph": 0,
        "grade_company": "PSA",
        "grade": 10,
        "serial_number": "",
    }


def test_topps_chrome_target_rejects_cosmic_chrome_listing():
    decision = MATCHER.match(
        _asset("Topps Chrome"),
        "2025 Topps Cosmic Chrome Shohei Ohtani #14 PSA 10",
    )
    assert decision.accepted is False
    assert decision.reason == "wrong_set_family"
    assert decision.diagnostics["conflicting_set_markers"] == ["cosmic"]


def test_cosmic_chrome_target_requires_cosmic_identity():
    decision = MATCHER.match(
        _asset("Topps Cosmic Chrome"),
        "2025 Topps Chrome Shohei Ohtani #14 PSA 10",
    )
    assert decision.accepted is False
    assert decision.reason == "set_family_not_confirmed"
    assert decision.diagnostics["target_set_markers"] == ["cosmic"]


def test_matching_cosmic_chrome_listing_accepts():
    decision = MATCHER.match(
        _asset("Topps Cosmic Chrome"),
        "2025 Topps Cosmic Chrome Shohei Ohtani #14 PSA 10",
    )
    assert decision.accepted is True
    assert decision.reason == "accepted"
