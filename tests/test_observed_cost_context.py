import pytest

from observed_cost_context import (
    CostContextPolicy,
    benchmark_cost_assumptions,
    derive_observed_cost_context,
)


def _contract(rows):
    return {"items": [{"evidence_ledger": {"accepted": rows}}]}


def _row(fee=None, liquidity=None, *, used=True, currency="USD"):
    row = {
        "used_in_valuation": used,
        "currency": currency,
        "price": 100,
    }
    if fee is not None:
        row["seller_fee_rate"] = fee
    if liquidity is not None:
        row["liquidity_haircut_rate"] = liquidity
    return row


def test_missing_context_fails_closed():
    context = derive_observed_cost_context(
        _contract([_row(), _row()]),
        policy=CostContextPolicy(min_fee_samples=2, min_liquidity_samples=2),
    )
    assert context["ready"] is False
    assert "insufficient_fee_samples" in context["blockers"]
    assert "insufficient_liquidity_samples" in context["blockers"]


def test_uses_only_accepted_usd_valuation_rows():
    rows = [
        _row(0.10, 0.02),
        _row(0.12, 0.03),
        _row(0.99, 0.99, used=False),
        _row(0.99, 0.99, currency="EUR"),
    ]
    context = derive_observed_cost_context(
        _contract(rows),
        policy=CostContextPolicy(min_fee_samples=2, min_liquidity_samples=2),
    )
    assert context["ready"] is True
    assert context["exit_fee_rate"] == pytest.approx(0.11)
    assert context["liquidity_haircut_rate"] == pytest.approx(0.025)


def test_out_of_range_values_are_rejected_not_clamped():
    rows = [
        _row(0.10, 0.02),
        _row(0.12, 0.03),
        _row(0.80, 0.90),
    ]
    context = derive_observed_cost_context(
        _contract(rows),
        policy=CostContextPolicy(min_fee_samples=2, min_liquidity_samples=2),
    )
    assert context["ready"] is True
    assert context["rejected_values"] == 2
    assert context["exit_fee_rate"] == pytest.approx(0.11)
    assert context["liquidity_haircut_rate"] == pytest.approx(0.025)


def test_benchmark_accessor_refuses_undersized_sample():
    with pytest.raises(RuntimeError):
        benchmark_cost_assumptions(
            _contract([_row(0.10, 0.02)]),
            policy=CostContextPolicy(min_fee_samples=2, min_liquidity_samples=2),
        )


def test_policy_validation():
    with pytest.raises(ValueError):
        CostContextPolicy(min_fee_samples=0)
