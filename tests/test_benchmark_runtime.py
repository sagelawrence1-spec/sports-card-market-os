import benchmark_runtime


def test_untrusted_cost_context_skips_without_touching_store(monkeypatch):
    monkeypatch.setattr(
        benchmark_runtime,
        "resolve_benchmark_cost_assumptions",
        lambda contract: {
            "ready": False,
            "source": None,
            "exit_fee_rate": None,
            "liquidity_haircut_rate": None,
            "blockers": ["missing_explicit_exit_fee_rate"],
        },
    )

    class ExplodingStore:
        def __init__(self, path):
            raise AssertionError("store must not be opened when costs are untrusted")

    monkeypatch.setattr(benchmark_runtime, "IntelligenceBenchmarkStore", ExplodingStore)
    result = benchmark_runtime.sync_benchmark_if_trustworthy(
        "market.sqlite", {"items": []}, horizon_days=30
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "untrusted_cost_assumptions"
    assert result["recorded"] == 0
    assert result["settled"] == 0


def test_trusted_cost_context_flows_into_journal(monkeypatch):
    monkeypatch.setattr(
        benchmark_runtime,
        "resolve_benchmark_cost_assumptions",
        lambda contract: {
            "ready": True,
            "source": "observed",
            "exit_fee_rate": 0.11,
            "liquidity_haircut_rate": 0.03,
            "blockers": [],
        },
    )

    captured = {}

    class FakeStore:
        def __init__(self, path):
            captured["database_path"] = path

    def fake_sync(store, contract, **kwargs):
        captured.update(kwargs)
        return {"recorded": 4, "settled": 2}

    monkeypatch.setattr(benchmark_runtime, "IntelligenceBenchmarkStore", FakeStore)
    monkeypatch.setattr(benchmark_runtime, "sync_contract_benchmark", fake_sync)

    result = benchmark_runtime.sync_benchmark_if_trustworthy(
        "market.sqlite", {"items": []}, horizon_days=45
    )

    assert captured["database_path"] == "market.sqlite"
    assert captured["horizon_days"] == 45
    assert captured["exit_fee_rate"] == 0.11
    assert captured["liquidity_haircut_rate"] == 0.03
    assert result["status"] == "recorded"
    assert result["recorded"] == 4
    assert result["settled"] == 2


def test_invalid_horizon_fails_fast():
    try:
        benchmark_runtime.sync_benchmark_if_trustworthy(
            "market.sqlite", {"items": []}, horizon_days=0
        )
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("expected ValueError")
