from datetime import date

from benchmark_journal import record_contract_observations, settle_matured_observations
from intelligence_benchmark import IntelligenceBenchmarkStore


def _contract(as_of, prices, *, fair_value=115.0, confidence=0.82):
    return {
        "generated_at": f"{as_of}T12:00:00",
        "items": [
            {
                "card_id": "card-1",
                "fair_value": fair_value,
                "confidence": confidence,
                "evidence_grade": "A",
                "last_updated": f"{as_of}T12:00:00",
                "evidence_ledger": {
                    "accepted": [
                        {
                            "price": price,
                            "currency": currency,
                            "event_date": sold_at,
                            "used_in_valuation": used,
                        }
                        for price, sold_at, currency, used in prices
                    ]
                },
            }
        ],
    }


def test_record_contract_observation_uses_only_accepted_usd_valuation_rows(tmp_path):
    store = IntelligenceBenchmarkStore(tmp_path / "market.sqlite")
    contract = _contract(
        "2026-01-01",
        [
            (100.0, "2025-12-20", "USD", True),
            (120.0, "2025-12-30", "USD", True),
            (500.0, "2025-12-31", "CAD", True),
            (999.0, "2025-12-31", "USD", False),
        ],
    )

    assert record_contract_observations(store, contract, horizon_days=30) == 1
    row = store.load_observations()[0]
    assert row.as_of_date == date(2026, 1, 1)
    assert row.current_price == 120.0
    assert row.baseline_estimate == 110.0
    assert row.intelligence_estimate == 115.0
    assert row.evidence_grade == "A"
    assert row.confidence == 0.82


def test_settlement_rejects_pre_horizon_sales_and_uses_first_mature_sale_day(tmp_path):
    store = IntelligenceBenchmarkStore(tmp_path / "market.sqlite")
    initial = _contract("2026-01-01", [(100.0, "2025-12-31", "USD", True)])
    record_contract_observations(store, initial, horizon_days=30)

    later = _contract(
        "2026-02-15",
        [
            (105.0, "2026-01-20", "USD", True),
            (130.0, "2026-02-01", "USD", True),
            (140.0, "2026-02-01", "USD", True),
            (150.0, "2026-02-10", "USD", True),
        ],
    )
    assert settle_matured_observations(store, later) == 1
    row = store.load_observations()[0]
    assert row.realized_at == date(2026, 2, 1)
    assert row.realized_price == 135.0


def test_observation_cost_assumptions_persist(tmp_path):
    store = IntelligenceBenchmarkStore(tmp_path / "market.sqlite")
    contract = _contract("2026-01-01", [(100.0, "2025-12-31", "USD", True)])
    record_contract_observations(
        store,
        contract,
        horizon_days=30,
        exit_fee_rate=0.13,
        liquidity_haircut_rate=0.04,
    )
    row = store.load_observations()[0]
    assert row.exit_fee_rate == 0.13
    assert row.liquidity_haircut_rate == 0.04
