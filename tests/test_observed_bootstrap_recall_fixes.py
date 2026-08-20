from entity_matcher import SportsCardEntityMatcher


def _asset(player, card_number, *, year=2025, set_name="Bowman Chrome"):
    return {
        "player": player,
        "year": year,
        "manufacturer": "Topps",
        "set_name": set_name,
        "card_number": card_number,
        "parallel": "base",
        "autograph": 1,
    }


def test_team_name_red_sox_does_not_masquerade_as_red_parallel():
    matcher = SportsCardEntityMatcher()
    asset = _asset("Franklin Arias", "CPA-FA")
    title = "2025 Bowman Chrome #CPA-FA Franklin Arias 1st Bowman Chrome Auto Boston Red Sox"
    decision = matcher.match(asset, title)
    assert decision.accepted is True, (decision.reason, decision.diagnostics)


def test_real_red_refractor_still_rejects_base_target():
    matcher = SportsCardEntityMatcher()
    asset = _asset("Franklin Arias", "CPA-FA")
    title = "2025 Bowman Chrome Red Refractor #CPA-FA Franklin Arias Auto /5"
    decision = matcher.match(asset, title)
    assert decision.accepted is False
    assert decision.reason in {"unexpected_parallel", "unexpected_serial_numbering"}


def test_hash_adjacent_to_chrome_does_not_break_set_identity():
    matcher = SportsCardEntityMatcher()
    asset = _asset("Bo Davidson", "CPA-BD")
    title = "2025 Bowman Chrome#CPA-BD Bo Davidson Autograph"
    decision = matcher.match(asset, title)
    assert decision.accepted is True, (decision.reason, decision.diagnostics)


def test_cpa_prospect_autographs_phrase_can_confirm_missing_catalog_number():
    matcher = SportsCardEntityMatcher()
    asset = _asset("Bo Davidson", "CPA-BD")
    title = "Bo Davidson 2025 Bowman Chrome Auto Prospect Autographs Card Giants"
    decision = matcher.match(asset, title)
    assert decision.accepted is True, (decision.reason, decision.diagnostics)


def test_named_non_prospect_auto_insert_cannot_use_cpa_fallback():
    matcher = SportsCardEntityMatcher()
    asset = _asset("Elian Pena", "CPA-EP")
    title = "2025 Bowman Chrome Elian Pena 1st Prime Signatures Auto /50 New York Mets"
    decision = matcher.match(asset, title)
    assert decision.accepted is False
