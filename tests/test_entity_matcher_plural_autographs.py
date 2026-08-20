from entity_matcher import SportsCardEntityMatcher


def _asset(player, card_number, *, year=2024, set_name="Bowman Chrome"):
    return {
        "player": player,
        "year": year,
        "manufacturer": "Topps",
        "set_name": set_name,
        "card_number": card_number,
        "parallel": "base",
        "autograph": 1,
    }


def test_plural_autographs_is_explicit_auto_evidence_when_identity_is_exact():
    matcher = SportsCardEntityMatcher()
    decision = matcher.match(
        _asset("George Wolkow", "CPA-GWO"),
        "2024 Bowman Chrome Prospect Autographs George Wolkow #CPA-GWO",
    )
    assert decision.accepted is True, (decision.reason, decision.diagnostics)


def test_plural_autographs_does_not_override_wrong_card_number():
    matcher = SportsCardEntityMatcher()
    decision = matcher.match(
        _asset("George Wolkow", "CPA-GWO"),
        "2024 Bowman Chrome Prospect Autographs George Wolkow #CPA-OTHER",
    )
    assert decision.accepted is False
    assert decision.reason == "wrong_card_number"


def test_plural_autographs_does_not_override_parallel_mismatch():
    matcher = SportsCardEntityMatcher()
    decision = matcher.match(
        _asset("George Wolkow", "CPA-GWO"),
        "2024 Bowman Chrome Prospect Autographs George Wolkow #CPA-GWO Refractor /499",
    )
    assert decision.accepted is False
    assert decision.reason in {"unexpected_parallel", "unexpected_serial_numbering"}
