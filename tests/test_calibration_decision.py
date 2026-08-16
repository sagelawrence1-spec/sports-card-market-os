import pytest

from calibration_decision import build_calibration_decision_record


def _history(allowed=True):
    return {
        "schema": "calibration-history.v1",
        "calibration_review_allowed": allowed,
        "automatic_threshold_changes_allowed": False,
        "decision": "human_review_allowed" if allowed else "blocked",
        "latest_evaluation_date": "2026-08-16",
        "latest_mature_observations": 42,
        "blockers": [] if allowed else ["unsafe_checkpoint:2026-08-16"],
    }


def test_records_proposal_without_applying_threshold_change():
    record = build_calibration_decision_record(
        _history(),
        decision="propose_change",
        reviewer="market-os-reviewer",
        reviewed_at="2026-08-16T15:00:00-07:00",
        rationale="Repeated mature evidence supports testing a narrower threshold.",
        proposals=[{"threshold": "buy_score", "current": 0.72, "proposed": 0.75}],
    )

    assert record["schema"] == "calibration-decision.v1"
    assert record["history_review_allowed"] is True
    assert record["proposals"] == [
        {"threshold": "buy_score", "current": 0.72, "proposed": 0.75}
    ]
    assert record["automatic_threshold_changes_allowed"] is False
    assert record["threshold_changes_applied"] is False
    assert record["record_id"].startswith("calibration-decision:")
    assert len(record["history_evidence_sha256"]) == 64


def test_same_evidence_and_decision_produce_stable_record_id():
    kwargs = dict(
        decision="no_change",
        reviewer="reviewer",
        reviewed_at="2026-08-16T15:00:00-07:00",
        rationale="No threshold change justified.",
    )
    first = build_calibration_decision_record(_history(), **kwargs)
    second = build_calibration_decision_record(_history(), **kwargs)
    assert first["record_id"] == second["record_id"]
    assert first["history_evidence_sha256"] == second["history_evidence_sha256"]


def test_blocked_history_cannot_propose_change():
    with pytest.raises(ValueError, match="review is blocked"):
        build_calibration_decision_record(
            _history(False),
            decision="propose_change",
            reviewer="reviewer",
            reviewed_at="2026-08-16T15:00:00-07:00",
            rationale="Trying to bypass the gate.",
            proposals=[{"threshold": "buy_score", "current": 0.72, "proposed": 0.75}],
        )


def test_propose_change_requires_actual_proposal():
    with pytest.raises(ValueError, match="requires at least one"):
        build_calibration_decision_record(
            _history(),
            decision="propose_change",
            reviewer="reviewer",
            reviewed_at="2026-08-16T15:00:00-07:00",
            rationale="Missing proposal should fail.",
        )


def test_non_change_decision_cannot_smuggle_proposals():
    with pytest.raises(ValueError, match="cannot include threshold proposals"):
        build_calibration_decision_record(
            _history(),
            decision="no_change",
            reviewer="reviewer",
            reviewed_at="2026-08-16T15:00:00-07:00",
            rationale="No change.",
            proposals=[{"threshold": "buy_score", "current": 0.72, "proposed": 0.75}],
        )


@pytest.mark.parametrize(
    "proposal",
    [
        {"threshold": "buy_score", "current": 0.72, "proposed": 0.72},
        {"threshold": "buy_score", "current": float("nan"), "proposed": 0.75},
    ],
)
def test_invalid_threshold_proposals_fail_closed(proposal):
    with pytest.raises(ValueError):
        build_calibration_decision_record(
            _history(),
            decision="propose_change",
            reviewer="reviewer",
            reviewed_at="2026-08-16T15:00:00-07:00",
            rationale="Invalid proposal.",
            proposals=[proposal],
        )


def test_duplicate_threshold_proposals_fail_closed():
    with pytest.raises(ValueError, match="duplicate threshold proposal"):
        build_calibration_decision_record(
            _history(),
            decision="propose_change",
            reviewer="reviewer",
            reviewed_at="2026-08-16T15:00:00-07:00",
            rationale="Duplicate proposals are ambiguous.",
            proposals=[
                {"threshold": "buy_score", "current": 0.72, "proposed": 0.74},
                {"threshold": "buy_score", "current": 0.72, "proposed": 0.76},
            ],
        )


def test_review_timestamp_must_be_timezone_aware():
    with pytest.raises(ValueError, match="include a timezone"):
        build_calibration_decision_record(
            _history(),
            decision="defer",
            reviewer="reviewer",
            reviewed_at="2026-08-16T15:00:00",
            rationale="Wait for more evidence.",
        )
