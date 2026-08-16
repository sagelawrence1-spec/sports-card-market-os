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


def test_base_target_rejects_image_variation_listing():
    decision = M.match(
        _base_asset(),
        "2024 Topps Chrome Shohei Ohtani #1 Image Variation PSA 10",
    )
    assert not decision.accepted
    assert decision.reason == "unexpected_parallel"
    assert "variation" in decision.diagnostics["unexpected_parallel"]


def test_variation_target_requires_variation_evidence():
    asset = _base_asset()
    asset["parallel"] = "Image Variation"
    decision = M.match(
        asset,
        "2024 Topps Chrome Shohei Ohtani #1 PSA 10",
    )
    assert not decision.accepted
    assert decision.reason == "manual_review"
    assert decision.diagnostics["review_reason"] == "parallel_not_confirmed"


def test_variation_target_accepts_explicit_variation_listing():
    asset = _base_asset()
    asset["parallel"] = "Image Variation"
    decision = M.match(
        asset,
        "2024 Topps Chrome Shohei Ohtani #1 Image Variation PSA 10",
    )
    assert decision.accepted
    assert decision.reason == "accepted"
