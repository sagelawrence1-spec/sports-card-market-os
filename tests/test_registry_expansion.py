import pytest

from registry_expansion import gate_registry_batch


def evaluation(*, blocked=False):
    good = {
        "rows": 20,
        "positive_labels": 10,
        "negative_labels": 10,
        "false_accepts": 0,
        "precision": 1.0,
        "recall": 0.9,
        "false_accept_rate": 0.0,
        "review_rate": 0.2,
    }
    bad = {**good, "false_accepts": 1, "precision": 0.9, "false_accept_rate": 0.1}
    return {
        "schema": "entity-resolution-eval.v1",
        "by_family": {
            "topps_chrome": good,
            "bowman_chrome": bad if blocked else good,
        },
    }


def card(card_id, family, *, player="Shohei Ohtani", year=2025, set_name="Topps Chrome", card_number="1"):
    return {
        "card_id": card_id,
        "family": family,
        "player": player,
        "year": year,
        "manufacturer": "Topps",
        "set_name": set_name,
        "card_number": card_number,
        "parallel": "base",
        "autograph": 0,
    }


def test_approves_atomic_batch_when_every_family_is_ready():
    result = gate_registry_batch(
        evaluation(),
        [
            card("tc-ohtani-1", "topps_chrome"),
            card("bc-ohtani-1", "bowman_chrome", set_name="Bowman Chrome"),
        ],
    )

    assert result["schema"] == "registry-batch-gate.v2"
    assert result["ready"] is True
    assert result["approved_card_ids"] == ["tc-ohtani-1", "bc-ohtani-1"]
    assert result["blocked_families"] == []


def test_one_unsafe_family_blocks_entire_batch():
    result = gate_registry_batch(
        evaluation(blocked=True),
        [
            card("tc-ohtani-1", "topps_chrome"),
            card("bc-ohtani-1", "bowman_chrome", set_name="Bowman Chrome"),
        ],
    )

    assert result["ready"] is False
    assert result["approved_card_ids"] == []
    assert result["blocked_families"] == ["bowman_chrome"]


def test_existing_card_id_blocks_batch_before_registry_mutation():
    result = gate_registry_batch(
        evaluation(),
        [card("tc-ohtani-1", "topps_chrome")],
        existing_card_ids={"tc-ohtani-1"},
    )

    assert result["ready"] is False
    assert result["record_blockers"][0]["blockers"] == ["card_id_already_exists"]


def test_duplicate_card_id_inside_batch_is_rejected():
    result = gate_registry_batch(
        evaluation(),
        [
            card("tc-ohtani-1", "topps_chrome", card_number="1"),
            card("tc-ohtani-1", "topps_chrome", card_number="2"),
        ],
    )

    assert result["ready"] is False
    assert result["record_blockers"][0]["index"] == 1
    assert result["record_blockers"][0]["blockers"] == ["duplicate_card_id_in_batch"]


def test_same_canonical_card_under_two_ids_is_rejected():
    result = gate_registry_batch(
        evaluation(),
        [
            card("tc-ohtani-a", "topps_chrome"),
            card("tc-ohtani-b", "topps_chrome"),
        ],
    )

    assert result["ready"] is False
    assert result["record_blockers"][0]["index"] == 1
    assert result["record_blockers"][0]["blockers"] == ["duplicate_canonical_identity_in_batch"]


def test_existing_canonical_identity_blocks_new_alias_id():
    existing = card("old-id", "topps_chrome")
    result = gate_registry_batch(
        evaluation(),
        [card("new-id", "topps_chrome")],
        existing_records=[existing],
    )

    assert result["ready"] is False
    assert result["record_blockers"][0]["blockers"] == ["canonical_identity_already_exists"]


def test_identity_normalization_catches_case_and_whitespace_collisions():
    existing = card("old-id", "topps_chrome")
    existing["player"] = "  SHOHEI   OHTANI "
    existing["set_name"] = "TOPPS CHROME"
    result = gate_registry_batch(
        evaluation(),
        [card("new-id", "topps_chrome")],
        existing_records=[existing],
    )

    assert result["ready"] is False
    assert result["record_blockers"][0]["blockers"] == ["canonical_identity_already_exists"]


def test_missing_identity_or_family_fails_closed():
    result = gate_registry_batch(
        evaluation(),
        [{"card_id": "", "family": ""}],
    )

    assert result["ready"] is False
    assert result["record_blockers"][0]["blockers"] == [
        "missing_card_id",
        "missing_family",
        "missing_or_invalid_canonical_identity",
    ]


def test_invalid_year_or_autograph_fails_closed():
    bad_year = card("tc-ohtani-1", "topps_chrome", year="unknown")
    bad_auto = card("tc-ohtani-2", "topps_chrome", card_number="2")
    bad_auto["autograph"] = "maybe"
    result = gate_registry_batch(evaluation(), [bad_year, bad_auto])

    assert result["ready"] is False
    assert all(
        item["blockers"] == ["missing_or_invalid_canonical_identity"]
        for item in result["record_blockers"]
    )


def test_empty_batch_is_not_ready():
    result = gate_registry_batch(evaluation(), [])
    assert result["ready"] is False
    assert result["approved_card_ids"] == []


def test_unsupported_evaluation_schema_fails_closed():
    with pytest.raises(ValueError, match="unsupported entity-resolution evaluation schema"):
        gate_registry_batch(
            {"schema": "wrong", "by_family": {"topps_chrome": {}}},
            [card("tc-ohtani-1", "topps_chrome")],
        )
