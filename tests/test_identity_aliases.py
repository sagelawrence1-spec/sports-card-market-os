from identity_aliases import AdjudicatedAliasRegistry, AliasAwareEntityRouter


def asset(**overrides):
    base = {
        "player": "Shohei Ohtani",
        "year": 2024,
        "manufacturer": "Topps",
        "set_name": "Topps Chrome",
        "card_number": "1",
        "parallel": "base",
        "grade_company": "PSA",
        "grade": 10,
        "autograph": 0,
        "serial_number": "",
    }
    base.update(overrides)
    return base


def test_alias_requires_two_independent_approvals():
    registry = AdjudicatedAliasRegistry()
    title = "2024 Topps Chrome Shohei Ohtani #1 PSA 10"

    registry.record_approval(title, "ohtani-1", "reviewer-a")
    assert registry.resolved_asset_id(title) is None

    # Duplicate approval from the same reviewer does not advance confidence.
    registry.record_approval(title, "ohtani-1", "reviewer-a")
    assert registry.resolved_asset_id(title) is None

    registry.record_approval(title, "ohtani-1", "reviewer-b")
    assert registry.resolved_asset_id(title) == "ohtani-1"
    assert registry.diagnostics(title)["active"] is True


def test_conflicting_approved_alias_fails_closed():
    registry = AdjudicatedAliasRegistry()
    title = "2024 Topps Chrome Shohei Ohtani #1 PSA 10"

    registry.record_approval(title, "asset-a", "reviewer-a")
    registry.record_approval(title, "asset-a", "reviewer-b")
    assert registry.resolved_asset_id(title) == "asset-a"

    registry.record_approval(title, "asset-b", "reviewer-c")
    assert registry.resolved_asset_id(title) is None
    assert registry.diagnostics(title)["conflicting"] is True


def test_rejection_revokes_alias_assignment():
    registry = AdjudicatedAliasRegistry()
    title = "2024 Topps Chrome Shohei Ohtani #1 PSA 10"
    registry.record_approval(title, "asset-a", "reviewer-a")
    registry.record_approval(title, "asset-a", "reviewer-b")
    assert registry.resolved_asset_id(title) == "asset-a"

    registry.record_rejection(title, "asset-a")
    assert registry.resolved_asset_id(title) is None


def test_verified_alias_cannot_override_hard_identity_conflict():
    registry = AdjudicatedAliasRegistry()
    # Human labels intentionally point this exact title at the wrong-year asset.
    # The alias may select the candidate, but the canonical matcher must reject it.
    title = "2023 Topps Chrome Shohei Ohtani #1 PSA 10"
    registry.record_approval(title, "ohtani-2024", "reviewer-a")
    registry.record_approval(title, "ohtani-2024", "reviewer-b")

    router = AliasAwareEntityRouter({"ohtani-2024": asset(year=2024)}, registry)
    decision = router.match(title)

    assert decision is not None
    assert decision.accepted is False
    assert decision.reason == "wrong_year"
    assert decision.diagnostics["alias_verified"] is True


def test_alias_router_accepts_only_after_canonical_matcher_passes():
    registry = AdjudicatedAliasRegistry()
    title = "2024 Topps Chrome Shohei Ohtani #1 PSA 10"
    registry.record_approval(title, "ohtani-1", "reviewer-a")
    registry.record_approval(title, "ohtani-1", "reviewer-b")

    router = AliasAwareEntityRouter({"ohtani-1": asset()}, registry)
    decision = router.match(title)

    assert decision is not None
    assert decision.accepted is True
    assert decision.reason == "accepted"
    assert decision.diagnostics["alias_candidate"] == "ohtani-1"
