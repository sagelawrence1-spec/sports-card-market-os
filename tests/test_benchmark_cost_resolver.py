import pytest

from benchmark_cost_resolver import resolve_benchmark_cost_assumptions


def _contract(rows):
    return {"items": [{"evidence_ledger": {"accepted": rows}}]}


def _row(fee=None, liquidity=None):
    row = {"used_in_valuation": True, "currency": "USD", "price": 100}
    if fee is not None:
        row["seller_fee_rate"] = fee
    if liquidity is not None:
        row["liquidity_haircut_rate"] = liquidity
    return row


def test_prefers_observed_context(monkeypatch):
    monkeypatch.setenv("BENCHMARK_EXIT_FEE_RATE", "0.25")
    monkeypatch.setenv("BENCHMARK_LIQUIDITY_HAIRCUT_RATE", "0.25")
    contract = _contract([
        _row(0.10, 0.02),
        _row(0.11, 0.03),
        _row(0.12, 0.04),
        _row(0.13, 0.05),
        _row(0.14, 0.06),
    ])
    result = resolve_benchmark_cost_assumptions(contract)
    assert result["ready"] is True
    assert result["source"] == "observed"
    assert result["exit_fee_rate"] == pytest.approx(0.12)
    assert result["liquidity_haircut_rate"] == pytest.approx(0.04)


def test_explicit_env_is_only_fallback(monkeypatch):
    monkeypatch.setenv("BENCHMARK_EXIT_FEE_RATE", "0.12")
    monkeypatch.setenv("BENCHMARK_LIQUIDITY_HAIRCUT_RATE", "0.03")
    result = resolve_benchmark_cost_assumptions(_contract([]))
    assert result["ready"] is True
    assert result["source"] == "explicit_env"
    assert result["exit_fee_rate"] == pytest.approx(0.12)
    assert result["liquidity_haircut_rate"] == pytest.approx(0.03)


def test_missing_observed_and_missing_env_fails_closed(monkeypatch):
    monkeypatch.delenv("BENCHMARK_EXIT_FEE_RATE", raising=False)
    monkeypatch.delenv("BENCHMARK_LIQUIDITY_HAIRCUT_RATE", raising=False)
    result = resolve_benchmark_cost_assumptions(_contract([]))
    assert result["ready"] is False
    assert "missing_explicit_exit_fee_rate" in result["blockers"]
    assert "missing_explicit_liquidity_haircut_rate" in result["blockers"]


def test_partial_env_configuration_still_fails_closed(monkeypatch):
    monkeypatch.setenv("BENCHMARK_EXIT_FEE_RATE", "0.12")
    monkeypatch.delenv("BENCHMARK_LIQUIDITY_HAIRCUT_RATE", raising=False)
    result = resolve_benchmark_cost_assumptions(_contract([]))
    assert result["ready"] is False
    assert "missing_explicit_liquidity_haircut_rate" in result["blockers"]


def test_invalid_explicit_fraction_raises(monkeypatch):
    monkeypatch.setenv("BENCHMARK_EXIT_FEE_RATE", "1.5")
    monkeypatch.setenv("BENCHMARK_LIQUIDITY_HAIRCUT_RATE", "0.03")
    with pytest.raises(ValueError):
        resolve_benchmark_cost_assumptions(_contract([]))
