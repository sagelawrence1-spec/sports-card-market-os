from entity_matcher import SportsCardEntityMatcher


M = SportsCardEntityMatcher()


def _base_asset():
    return {
        "year": 2024,
        "manufacturer": "Topps",
        "set_name": "Chrome",
        "player": "Shohei Ohtani",
        "card_number": "1",
        "parallel": "Base",
        "autograph": 0,
        "grade_company": "PSA",
        "grade": 10,
        "serial_number": "",
    }


def test_non_numbered_target_rejects_numbered_listing():
    decision = M.match(
        _base_asset(),
        "2024 Topps Chrome Shohei Ohtani #1 /499 PSA 10",
    )
    assert not decision.accepted
    assert decision.reason == "unexpected_serial_numbering"
    assert decision.diagnostics["unexpected_serial_denominators"] == ["499"]


def test_non_numbered_target_accepts_plain_listing():
    decision = M.match(
        _base_asset(),
        "2024 Topps Chrome Shohei Ohtani #1 PSA 10",
    )
    assert decision.accepted
    assert decision.reason == "accepted"
    assert decision.diagnostics["explicit_serial_denominators"] == []


def test_numbered_target_still_accepts_matching_denominator():
    asset = _base_asset()
    asset["parallel"] = "Gold"
    asset["serial_number"] = "50"
    decision = M.match(
        asset,
        "2024 Topps Chrome Shohei Ohtani #1 Gold Refractor /50 PSA 10",
    )
    assert decision.accepted
    assert decision.diagnostics["serial_denominator_match"] == 1
