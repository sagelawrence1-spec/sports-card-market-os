import pytest

from calibration_decision import build_calibration_decision_record


def _history():
    return {
        "schema": "calibration-history.v1",
        "calibration_review_allowed": True,
        "automatic_threshold_changes_allowed": False,
        "decision": "human_review_allowed",
        "latest_evaluation_date": "2026-08-16",
        "latest_mature_observations": 42,
        "blockers": [],
    }


@pytest.mark.parametrize("reviewer", [True, 7, 3.14])
def test_reviewer_identity_must_be_text(reviewer):
    with pytest.raises(ValueError, match="reviewer is required"):
        build_calibration_decision_record(
            _history(),
            decision="no_change",
            reviewer=reviewer,
            reviewed_at="2026-08-16T15:00:00-07:00",
            rationale="No change justified.",
        )


@pytest.mark.parametrize("rationale", [True, 7, 3.14])
def test_rationale_must_be_text(rationale):
    with pytest.raises(ValueError, match="rationale is required"):
        build_calibration_decision_record(
            _history(),
            decision="no_change",
            reviewer="reviewer",
            reviewed_at="2026-08-16T15:00:00-07:00",
            rationale=rationale,
        )


@pytest.mark.parametrize("threshold", [True, 7, 3.14])
def test_threshold_identity_must_be_text(threshold):
    with pytest.raises(ValueError, match="requires threshold"):
        build_calibration_decision_record(
            _history(),
            decision="propose_change",
            reviewer="reviewer",
            reviewed_at="2026-08-16T15:00:00-07:00",
            rationale="Test threshold adjustment.",
            proposals=[{"threshold": threshold, "current": 0.72, "proposed": 0.75}],
        )


def test_text_identity_fields_are_trimmed_deterministically():
    record = build_calibration_decision_record(
        _history(),
        decision="propose_change",
        reviewer="  reviewer  ",
        reviewed_at="2026-08-16T15:00:00-07:00",
        rationale="  Test threshold adjustment.  ",
        proposals=[{"threshold": "  buy_score  ", "current": 0.72, "proposed": 0.75}],
    )

    assert record["reviewer"] == "reviewer"
    assert record["rationale"] == "Test threshold adjustment."
    assert record["proposals"][0]["threshold"] == "buy_score"
