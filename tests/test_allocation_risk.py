import pytest

from allocation_risk import AllocationRiskProfile, apply_candidate_risk


def test_candidate_risk_haircuts_approved_allocation_without_increasing_it():
    allocations = [{"card_id": "card-1", "allocation": 1000.0, "ready": True, "blockers": []}]
    profiles = {
        "card-1": AllocationRiskProfile(
            card_id="card-1",
            liquidity_score=0.80,
            downside_pct=0.25,
        )
    }

    result = apply_candidate_risk(allocations, profiles, portfolio_value=10_000)[0]

    assert result["risk_multiplier"] == 0.60
    assert result["risk_adjusted_allocation"] == 600.0
    assert result["risk_adjusted_allocation_pct"] == 0.06
    assert result["risk_adjusted_allocation"] <= result["allocation"]


def test_missing_candidate_risk_profile_fails_closed():
    allocations = [{"card_id": "card-1", "allocation": 1000.0, "ready": True, "blockers": []}]

    result = apply_candidate_risk(allocations, {}, portfolio_value=10_000)[0]

    assert result["risk_adjusted_allocation"] == 0.0
    assert result["risk_blockers"] == ["missing_candidate_risk_profile"]


def test_zero_liquidity_blocks_incremental_capital():
    allocations = [{"card_id": "card-1", "allocation": 1000.0, "ready": True, "blockers": []}]
    profiles = {"card-1": AllocationRiskProfile("card-1", liquidity_score=0.0, downside_pct=0.10)}

    result = apply_candidate_risk(allocations, profiles, portfolio_value=10_000)[0]

    assert result["risk_adjusted_allocation"] == 0.0
    assert "no_liquidity_capacity" in result["risk_blockers"]


def test_total_downside_risk_blocks_incremental_capital():
    allocations = [{"card_id": "card-1", "allocation": 1000.0, "ready": True, "blockers": []}]
    profiles = {"card-1": AllocationRiskProfile("card-1", liquidity_score=0.90, downside_pct=1.0)}

    result = apply_candidate_risk(allocations, profiles, portfolio_value=10_000)[0]

    assert result["risk_adjusted_allocation"] == 0.0
    assert "total_downside_risk" in result["risk_blockers"]


def test_rejected_base_allocation_stays_at_zero():
    allocations = [{"card_id": "card-1", "allocation": 500.0, "ready": False, "blockers": ["segment_sample_too_small"]}]
    profiles = {"card-1": AllocationRiskProfile("card-1", liquidity_score=1.0, downside_pct=0.0)}

    result = apply_candidate_risk(allocations, profiles, portfolio_value=10_000)[0]

    assert result["risk_adjusted_allocation"] == 0.0
    assert result["risk_blockers"] == ["segment_sample_too_small"]


@pytest.mark.parametrize(
    "liquidity,downside",
    [
        (float("nan"), 0.1),
        (float("inf"), 0.1),
        (-0.1, 0.1),
        (1.1, 0.1),
        (0.8, float("nan")),
        (0.8, -0.1),
        (0.8, 1.1),
        (True, 0.1),
    ],
)
def test_invalid_candidate_risk_metadata_fails_closed(liquidity, downside):
    with pytest.raises(ValueError):
        AllocationRiskProfile("card-1", liquidity_score=liquidity, downside_pct=downside)


def test_invalid_portfolio_value_fails_closed():
    allocations = [{"card_id": "card-1", "allocation": 1000.0, "ready": True, "blockers": []}]
    profiles = {"card-1": AllocationRiskProfile("card-1", liquidity_score=1.0, downside_pct=0.0)}

    with pytest.raises(ValueError):
        apply_candidate_risk(allocations, profiles, portfolio_value=float("nan"))
