from datetime import date

from capital_allocation import (
    AllocationCandidate,
    AllocationPolicy,
    allocation_readiness,
    size_candidates,
)
from recommendation_journal import Recommendation, RecommendationJournal


def _row(
    idx,
    *,
    action="BUY",
    evidence_grade="A",
    confidence=0.85,
    entry=100.0,
    realized=110.0,
):
    return Recommendation(
        observation_id=f"obs-{idx}",
        card_id=f"card-{idx}",
        as_of_date=date(2026, 1, 1),
        action=action,
        entry_price=entry,
        fair_value=120.0,
        confidence=confidence,
        evidence_grade=evidence_grade,
        thesis="test",
        horizon_days=30,
        realized_price=realized,
        realized_at=date(2026, 2, 1),
    )


def _journal(tmp_path, rows):
    journal = RecommendationJournal(tmp_path / "market.sqlite")
    for row in rows:
        journal.upsert(row)
    return journal


def _policy():
    return AllocationPolicy(
        min_overall_settled=6,
        min_action_settled=4,
        min_segment_settled=3,
        min_hit_rate=0.60,
        min_median_return=0.02,
        max_position_pct=0.10,
        max_total_deployment_pct=0.25,
    )


def test_allocation_fails_closed_when_realized_sample_is_too_small(tmp_path):
    journal = _journal(tmp_path, [_row(1), _row(2)])
    candidate = AllocationCandidate("new", "BUY", 100, 120, 0.85, "A")
    result = allocation_readiness(journal, candidate, policy=_policy())
    assert result["ready"] is False
    assert "overall_sample_too_small" in result["blockers"]
    assert "action_sample_too_small" in result["blockers"]
    assert "segment_sample_too_small" in result["blockers"]


def test_bad_realized_track_record_blocks_capital_even_with_strong_upside(tmp_path):
    rows = [
        _row(1, realized=90),
        _row(2, realized=92),
        _row(3, realized=95),
        _row(4, realized=93),
        _row(5, action="ACCUMULATE", realized=110),
        _row(6, action="ACCUMULATE", realized=111),
    ]
    journal = _journal(tmp_path, rows)
    candidate = AllocationCandidate("new", "BUY", 100, 150, 0.90, "A")
    result = allocation_readiness(journal, candidate, policy=_policy())
    assert result["ready"] is False
    assert "action_hit_rate_below_floor" in result["blockers"]
    assert "action_median_return_below_floor" in result["blockers"]


def test_candidate_specific_segment_must_be_proven(tmp_path):
    rows = [
        _row(1), _row(2), _row(3), _row(4),
        _row(5, action="ACCUMULATE"),
        _row(6, action="ACCUMULATE"),
    ]
    journal = _journal(tmp_path, rows)
    candidate = AllocationCandidate("new", "BUY", 100, 120, 0.70, "B")
    result = allocation_readiness(journal, candidate, policy=_policy())
    assert result["ready"] is False
    assert "segment_sample_too_small" in result["blockers"]


def test_sizing_respects_position_and_total_deployment_caps(tmp_path):
    rows = [
        _row(1), _row(2), _row(3), _row(4),
        _row(5, action="ACCUMULATE"),
        _row(6, action="ACCUMULATE"),
        _row(7, action="ACCUMULATE"),
        _row(8, action="ACCUMULATE"),
    ]
    journal = _journal(tmp_path, rows)
    candidates = [
        AllocationCandidate("a", "BUY", 100, 140, 0.90, "A"),
        AllocationCandidate("b", "BUY", 100, 130, 0.85, "A"),
        AllocationCandidate("c", "ACCUMULATE", 100, 125, 0.85, "A"),
    ]
    allocations = size_candidates(
        journal,
        candidates,
        portfolio_value=10_000,
        policy=_policy(),
    )
    approved = [row for row in allocations if row["ready"]]
    assert approved
    assert all(row["allocation"] <= 1_000 for row in approved)
    assert sum(row["allocation"] for row in approved) <= 2_500


def test_hold_does_not_receive_incremental_capital(tmp_path):
    rows = [_row(i) for i in range(1, 7)]
    journal = _journal(tmp_path, rows)
    candidate = AllocationCandidate("hold", "HOLD", 100, 120, 0.90, "A")
    result = size_candidates(
        journal,
        [candidate],
        portfolio_value=10_000,
        policy=_policy(),
    )[0]
    assert result["ready"] is False
    assert result["allocation"] == 0
    assert "non_deploy_action" in result["blockers"]
