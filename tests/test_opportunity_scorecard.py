import pytest

from opportunity_scorecard import OpportunityScorecardPolicy, build_opportunity_scorecard


def outcome(player, card, decision_as_of, net_return, grade, decision="START_POSITION", latency_bucket=None):
    row = {
        "schema": "opportunity-outcome.v1",
        "player_id": player,
        "card_id": card,
        "catalyst_at": "2026-08-01T12:00:00+00:00",
        "decision_as_of": decision_as_of,
        "decision": decision,
        "net_return": net_return,
        "grade": grade,
        "hit": net_return >= 0.0,
    }
    if latency_bucket is not None:
        row["decision_latency_bucket"] = latency_bucket
    return row


def test_scorecard_meets_repeated_positive_evidence_threshold():
    rows = [
        outcome("p1", "c1", "2026-08-02T00:00:00+00:00", 0.20, "A", latency_bucket="UNDER_6H"),
        outcome("p2", "c2", "2026-08-03T00:00:00+00:00", 0.12, "B", latency_bucket="UNDER_6H"),
        outcome("p3", "c3", "2026-08-04T00:00:00+00:00", 0.05, "C", latency_bucket="6_TO_24H"),
        outcome("p4", "c4", "2026-08-05T00:00:00+00:00", -0.03, "D", latency_bucket="OVER_24H"),
        outcome("p5", "c5", "2026-08-06T00:00:00+00:00", 0.08, "C", decision="ADD", latency_bucket="OVER_24H"),
    ]
    scorecard = build_opportunity_scorecard(rows)
    assert scorecard["schema"] == "opportunity-scorecard.v1"
    assert scorecard["status"] == "EVIDENCE_THRESHOLD_MET"
    assert scorecard["settled_outcomes"] == 5
    assert scorecard["distinct_players"] == 5
    assert scorecard["hit_rate"] == pytest.approx(0.8)
    assert scorecard["median_net_return"] == pytest.approx(0.08)
    assert scorecard["grade_distribution"]["A"] == 1
    assert scorecard["by_decision"]["ADD"]["count"] == 1
    assert scorecard["by_decision_latency"]["UNDER_6H"]["count"] == 2
    assert scorecard["by_decision_latency"]["UNDER_6H"]["hit_rate"] == 1.0
    assert scorecard["by_decision_latency"]["OVER_24H"]["median_net_return"] == pytest.approx(0.025)


def test_scorecard_marks_legacy_outcome_latency_unknown():
    scorecard = build_opportunity_scorecard(
        [outcome("p1", "c1", "2026-08-02T00:00:00+00:00", 0.1, "B")]
    )
    assert scorecard["by_decision_latency"]["UNKNOWN"]["count"] == 1


def test_scorecard_rejects_invalid_latency_bucket():
    row = outcome(
        "p1", "c1", "2026-08-02T00:00:00+00:00", 0.1, "B", latency_bucket="FASTISH"
    )
    with pytest.raises(ValueError, match="latency bucket"):
        build_opportunity_scorecard([row])


def test_scorecard_does_not_overclaim_thin_sample():
    rows = [outcome("p1", "c1", "2026-08-02T00:00:00+00:00", 0.40, "A")]
    scorecard = build_opportunity_scorecard(rows)
    assert scorecard["status"] == "INSUFFICIENT_EVIDENCE"
    assert "insufficient_settled_outcomes" in scorecard["proof_blockers"]
    assert "insufficient_distinct_players" in scorecard["proof_blockers"]


def test_scorecard_requires_breadth_even_with_enough_rows():
    rows = [
        outcome("p1", f"c{i}", f"2026-08-{i+2:02d}T00:00:00+00:00", 0.1, "B")
        for i in range(5)
    ]
    scorecard = build_opportunity_scorecard(rows)
    assert scorecard["status"] == "INSUFFICIENT_EVIDENCE"
    assert scorecard["proof_blockers"] == ["insufficient_distinct_players"]


def test_scorecard_rejects_duplicate_decision_identity():
    row = outcome("p1", "c1", "2026-08-02T00:00:00+00:00", 0.1, "B")
    with pytest.raises(ValueError, match="duplicate"):
        build_opportunity_scorecard([row, dict(row)])


def test_scorecard_rejects_inconsistent_hit_flag():
    row = outcome("p1", "c1", "2026-08-02T00:00:00+00:00", -0.1, "D")
    row["hit"] = True
    with pytest.raises(ValueError, match="inconsistent"):
        build_opportunity_scorecard([row])


def test_scorecard_rejects_non_actionable_outcome():
    row = outcome("p1", "c1", "2026-08-02T00:00:00+00:00", 0.1, "B")
    row["decision"] = "WATCH_FOR_COMPS"
    with pytest.raises(ValueError, match="actionable"):
        build_opportunity_scorecard([row])


def test_scorecard_policy_can_raise_evidence_bar():
    rows = [
        outcome(f"p{i}", f"c{i}", f"2026-08-{i+2:02d}T00:00:00+00:00", value, grade)
        for i, (value, grade) in enumerate([(0.2, "A"), (0.1, "B"), (0.05, "C"), (-0.01, "D"), (-0.02, "D")], start=1)
    ]
    scorecard = build_opportunity_scorecard(
        rows,
        policy=OpportunityScorecardPolicy(min_hit_rate=0.9, min_median_net_return=0.1),
    )
    assert scorecard["status"] == "INSUFFICIENT_EVIDENCE"
    assert "hit_rate_below_threshold" in scorecard["proof_blockers"]
    assert "median_net_return_below_threshold" in scorecard["proof_blockers"]


@pytest.mark.parametrize(
    "policy",
    [
        OpportunityScorecardPolicy(min_settled_outcomes=0),
        OpportunityScorecardPolicy(min_distinct_players=0),
        OpportunityScorecardPolicy(min_hit_rate=1.1),
        OpportunityScorecardPolicy(min_median_net_return=float("nan")),
    ],
)
def test_scorecard_policy_fails_closed(policy):
    with pytest.raises(ValueError):
        build_opportunity_scorecard(
            [outcome("p1", "c1", "2026-08-02T00:00:00+00:00", 0.1, "B")],
            policy=policy,
        )
