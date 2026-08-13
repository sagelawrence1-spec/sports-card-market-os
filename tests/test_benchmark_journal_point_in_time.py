from datetime import date

from benchmark_journal import record_contract_observations, settle_matured_observations
from intelligence_benchmark import IntelligenceBenchmarkStore


def contract(as_of, rows):
    return {
        "generated_at": f"{as_of}T12:00:00",
        "items": [{
            "card_id": "card-1",
            "fair_value": 115.0,
            "confidence": 0.82,
            "evidence_grade": "A",
            "last_updated": f"{as_of}T12:00:00",
            "evidence_ledger": {"accepted": [
                {"price": p, "currency": "USD", "event_date": d, "used_in_valuation": True}
                for p, d in rows
            ]},
        }],
    }


def test_future_rows_do_not_enter_point_in_time_baseline(tmp_path):
    store = IntelligenceBenchmarkStore(tmp_path / "market.sqlite")
    assert record_contract_observations(store, contract("2026-01-01", [
        (100.0, "2025-12-20"),
        (120.0, "2025-12-30"),
        (999.0, "2026-01-05"),
    ])) == 1
    row = store.load_observations()[0]
    assert row.current_price == 120.0
    assert row.baseline_estimate == 110.0


def test_future_only_rows_cannot_create_observation(tmp_path):
    store = IntelligenceBenchmarkStore(tmp_path / "market.sqlite")
    assert record_contract_observations(
        store, contract("2026-01-01", [(999.0, "2026-01-05")])
    ) == 0
    assert store.load_observations() == []


def test_settlement_stops_at_evaluation_date(tmp_path):
    store = IntelligenceBenchmarkStore(tmp_path / "market.sqlite")
    record_contract_observations(
        store, contract("2026-01-01", [(100.0, "2025-12-31")]), horizon_days=30
    )
    later = contract("2026-02-01", [
        (130.0, "2026-02-01"),
        (999.0, "2026-02-10"),
    ])
    assert settle_matured_observations(store, later) == 1
    row = store.load_observations()[0]
    assert row.realized_at == date(2026, 2, 1)
    assert row.realized_price == 130.0
