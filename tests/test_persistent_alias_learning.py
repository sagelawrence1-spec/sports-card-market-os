from entity_matcher import MatchDecision, norm
from evidence_store import EvidenceStore
from identity_aliases import AliasAwareEntityRouter, PersistentAliasRegistry
from providers.base import EvidenceRecord


TITLE = "2024 Topps Chrome Shohei Ohtani #1 PSA 10"
ASSET = {
    "card_id": "ohtani-1",
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


def queue_review(store, source_item_id, title=TITLE, card_id="ohtani-1"):
    record = EvidenceRecord(
        "ebay_product_research",
        "sold",
        source_item_id,
        title,
        100.0,
        "2026-08-01",
        currency="USD",
    )
    decision = MatchDecision(False, 70.0, "manual_review", {"candidate": card_id})
    return store.save(record, card_id, "ohtani", decision)


def test_review_approvals_persist_and_require_independent_reviewers(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    first = queue_review(store, "sale-1")
    second = queue_review(store, "sale-2")

    assert store.adjudicate(first, True, reviewer_id="reviewer-a")
    assert store.resolved_alias_asset_id(TITLE) is None

    assert store.adjudicate(second, True, reviewer_id="reviewer-b")
    assert store.resolved_alias_asset_id(TITLE) == "ohtani-1"

    reopened = EvidenceStore(tmp_path / "evidence.sqlite")
    assert reopened.resolved_alias_asset_id(TITLE) == "ohtani-1"
    assert reopened.alias_diagnostics(TITLE)["approval_counts"] == {"ohtani-1": 2}


def test_duplicate_reviewer_does_not_double_count(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    first = queue_review(store, "sale-1")
    second = queue_review(store, "sale-2")

    assert store.adjudicate(first, True, reviewer_id="reviewer-a")
    assert store.adjudicate(second, True, reviewer_id="reviewer-a")

    diagnostics = store.alias_diagnostics(TITLE)
    assert diagnostics["approval_counts"] == {"ohtani-1": 1}
    assert diagnostics["active"] is False


def test_evidence_store_normalizes_legacy_alias_identity_variants(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    store.conn.executemany(
        """INSERT INTO identity_alias_adjudications(
        title_key,title,asset_id,reviewer_id,approved,evidence_id
        ) VALUES(?,?,?,?,?,?)""",
        [
            (norm(TITLE), TITLE, "ohtani-1", "reviewer-a", 1, "legacy-1"),
            (norm(TITLE), TITLE, " ohtani-1 ", " reviewer-a ", 1, "legacy-2"),
            (norm(TITLE), TITLE, "ohtani-1 ", "reviewer-b", 1, "legacy-3"),
        ],
    )
    store.conn.commit()

    diagnostics = store.alias_diagnostics(TITLE)

    assert diagnostics["approval_counts"] == {"ohtani-1": 2}
    assert diagnostics["conflicting"] is False
    assert diagnostics["active"] is True
    assert store.resolved_alias_asset_id(TITLE) == "ohtani-1"


def test_evidence_store_fails_closed_on_blank_legacy_alias_identity(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    store.conn.execute(
        """INSERT INTO identity_alias_adjudications(
        title_key,title,asset_id,reviewer_id,approved,evidence_id
        ) VALUES(?,?,?,?,?,?)""",
        (norm(TITLE), TITLE, "ohtani-1", "   ", 1, "legacy-blank"),
    )
    store.conn.commit()

    try:
        store.alias_diagnostics(TITLE)
    except ValueError as exc:
        assert "cannot be blank" in str(exc)
    else:
        raise AssertionError("blank persisted alias identities must fail closed")


def test_persistent_registry_normalizes_legacy_identity_variants(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    store.conn.executemany(
        """INSERT INTO identity_alias_adjudications(
        title_key,title,asset_id,reviewer_id,approved,evidence_id
        ) VALUES(?,?,?,?,?,?)""",
        [
            (norm(TITLE), TITLE, "ohtani-1", "reviewer-a", 1, "legacy-1"),
            (norm(TITLE), TITLE, " ohtani-1 ", " reviewer-a ", 1, "legacy-2"),
            (norm(TITLE), TITLE, "ohtani-1 ", "reviewer-b", 1, "legacy-3"),
        ],
    )
    store.conn.commit()

    registry = PersistentAliasRegistry(store)
    diagnostics = registry.diagnostics(TITLE)

    assert diagnostics["approval_counts"] == {"ohtani-1": 2}
    assert diagnostics["conflicting"] is False
    assert diagnostics["active"] is True
    assert registry.resolved_asset_id(TITLE) == "ohtani-1"


def test_any_verified_rejection_blocks_alias_activation(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    ids = [queue_review(store, f"sale-{index}") for index in range(3)]

    assert store.adjudicate(ids[0], True, reviewer_id="reviewer-a")
    assert store.adjudicate(ids[1], True, reviewer_id="reviewer-b")
    assert store.resolved_alias_asset_id(TITLE) == "ohtani-1"

    assert store.adjudicate(ids[2], False, reviewer_id="reviewer-c")
    diagnostics = store.alias_diagnostics(TITLE)
    assert diagnostics["rejection_counts"] == {"ohtani-1": 1}
    assert diagnostics["active"] is False
    assert store.resolved_alias_asset_id(TITLE) is None


def test_persistent_alias_router_still_requires_canonical_match(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    ids = [queue_review(store, f"sale-{index}") for index in range(2)]
    assert store.adjudicate(ids[0], True, reviewer_id="reviewer-a")
    assert store.adjudicate(ids[1], True, reviewer_id="reviewer-b")

    registry = PersistentAliasRegistry(store)
    router = AliasAwareEntityRouter({"ohtani-1": ASSET}, registry)
    accepted = router.match(TITLE)
    assert accepted is not None and accepted.accepted is True
    assert accepted.diagnostics["alias_verified"] is True

    wrong_year = TITLE.replace("2024", "2023")
    wrong_ids = [queue_review(store, f"wrong-{index}", title=wrong_year) for index in range(2)]
    assert store.adjudicate(wrong_ids[0], True, reviewer_id="reviewer-a")
    assert store.adjudicate(wrong_ids[1], True, reviewer_id="reviewer-b")

    rejected = router.match(wrong_year)
    assert rejected is not None and rejected.accepted is False
    assert rejected.reason == "wrong_year"