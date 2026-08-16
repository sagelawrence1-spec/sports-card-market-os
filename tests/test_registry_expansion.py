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


def test_approves_atomic_batch_when_every_family_is_ready():
    result = gate_registry_batch(
        evaluation(),
        [
            {"card_id": "tc-ohtani-1", "family": "topps_chrome"},
            {"card_id": "bc-ohtani-1", "family": "bowman_chrome"},
        ],
    )

    assert result["ready"] is True
    assert result["approved_card_ids"] == ["tc-ohtani-1", "bc-ohtani-1"]
    assert result["blocked_families"] == []


def test_one_unsafe_family_blocks_entire_batch():
    result = gate_registry_batch(
        evaluation(blocked=True),
        [
            {"card_id": "tc-ohtani-1", "family": "topps_chrome"},
            {"card_id": "bc-ohtani-1", "family": "bowman_chrome"},
        ],
    )

    assert result["ready"] is False
    assert result["approved_card_ids"] == []
    assert result["blocked_families"] == ["bowman_chrome"]


def test_existing_identity_blocks_batch_before_registry_mutation():
    result = gate_registry_batch(
        evaluation(),
        [{"card_id": "tc-ohtani-1", "family": "topps_chrome"}],
        existing_card_ids={"tc-ohtani-1"},
    )

    assert result["ready"] is False
    assert result["record_blockers"][0]["blockers"] == ["card_id_already_exists"]


def test_duplicate_identity_inside_batch_is_rejected():
    result = gate_registry_batch(
        evaluation(),
        [
            {"card_id": "tc-ohtani-1", "family": "topps_chrome"},
            {"card_id": "tc-ohtani-1", "family": "topps_chrome"},
        ],
    )

    assert result["ready"] is False
    assert result["record_blockers"][0]["index"] == 1
    assert result["record_blockers"][0]["blockers"] == ["duplicate_card_id_in_batch"]


def test_missing_identity_or_family_fails_closed():
    result = gate_registry_batch(
        evaluation(),
        [{"card_id": "", "family": ""}],
    )

    assert result["ready"] is False
    assert result["record_blockers"][0]["blockers"] == ["missing_card_id", "missing_family"]


def test_empty_batch_is_not_ready():
    result = gate_registry_batch(evaluation(), [])
    assert result["ready"] is False
    assert result["approved_card_ids"] == []


def test_unsupported_evaluation_schema_fails_closed():
    with pytest.raises(ValueError, match="unsupported entity-resolution evaluation schema"):
        gate_registry_batch(
            {"schema": "wrong", "by_family": {"topps_chrome": {}}},
            [{"card_id": "tc-ohtani-1", "family": "topps_chrome"}],
        )
