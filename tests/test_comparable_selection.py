import pytest

from comparable_selection import ComparablePolicy, select_hierarchy_comparables


def card(card_id, **overrides):
    row = {
        "card_id": card_id,
        "player": "Shohei Ohtani",
        "sport": "baseball",
        "manufacturer": "Topps",
        "product_family": "Topps Chrome",
        "year": 2025,
        "grader": "PSA",
        "grade": 10,
        "rookie_flag": False,
        "autograph": False,
        "serial_number": 50,
        "parallel_family": "gold refractor",
    }
    row.update(overrides)
    return row


def test_selects_nearest_same_identity_hierarchy_comps_deterministically():
    target = card("target")
    candidates = [
        card("older", year=2023),
        card("best-b", year=2025),
        card("best-a", year=2025),
    ]
    result = select_hierarchy_comparables(target, candidates, policy=ComparablePolicy(max_results=2))
    assert result["schema"] == "comparable-selection.v1"
    assert [row["card_id"] for row in result["selected"]] == ["best-a", "best-b"]
    assert {row["card_id"]: row["reason"] for row in result["rejected"]}["older"] == "ranked_out"


def test_fails_closed_on_player_product_and_grade_mismatch():
    target = card("target")
    candidates = [
        card("wrong-player", player="Aaron Judge"),
        card("wrong-family", product_family="Topps Update"),
        card("wrong-grade", grade=9),
    ]
    result = select_hierarchy_comparables(target, candidates)
    reasons = {row["card_id"]: row["reason"] for row in result["rejected"]}
    assert reasons == {
        "wrong-player": "player_mismatch",
        "wrong-family": "product_family_mismatch",
        "wrong-grade": "grade_mismatch",
    }
    assert result["selected"] == []


def test_rejects_far_years_and_incomplete_identity():
    target = card("target")
    result = select_hierarchy_comparables(
        target,
        [card("old", year=2019), {"card_id": "partial", "player": "Shohei Ohtani"}],
    )
    reasons = {row["card_id"]: row["reason"] for row in result["rejected"]}
    assert reasons["old"] == "year_distance"
    assert reasons["partial"] == "incomplete_identity"


def test_serial_scarcity_and_parallel_identity_affect_rank_without_becoming_hardcoded_value():
    target = card("target", serial_number=50, parallel_family="gold refractor")
    result = select_hierarchy_comparables(
        target,
        [
            card("close", serial_number=75, parallel_family="gold refractor"),
            card("loose", serial_number=499, parallel_family="blue refractor"),
        ],
        policy=ComparablePolicy(min_score=40),
    )
    assert [row["card_id"] for row in result["selected"]] == ["close", "loose"]
    assert result["selected"][0]["score"] > result["selected"][1]["score"]


def test_duplicate_candidates_cannot_double_weight_selection():
    target = card("target")
    result = select_hierarchy_comparables(target, [card("dup"), card("dup")])
    assert [row["card_id"] for row in result["selected"]] == ["dup"]
    assert {row["reason"] for row in result["rejected"]} == {"duplicate_candidate"}


def test_raw_and_graded_hierarchy_do_not_cross():
    target = card("raw", grader="", grade=None)
    result = select_hierarchy_comparables(target, [card("psa"), card("raw-peer", grader="", grade=None)])
    assert [row["card_id"] for row in result["selected"]] == ["raw-peer"]
    assert {row["card_id"]: row["reason"] for row in result["rejected"]}["psa"] == "grader_mismatch"


def test_invalid_target_or_policy_fails_closed():
    with pytest.raises(ValueError):
        select_hierarchy_comparables({"card_id": "x"}, [])
    with pytest.raises(ValueError):
        select_hierarchy_comparables(card("target"), [], policy=ComparablePolicy(max_results=0))
