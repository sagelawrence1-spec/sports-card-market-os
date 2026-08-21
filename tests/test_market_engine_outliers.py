from market_engine import estimate_market, valuation_sample


def _sale(evidence_id, price, sold_date="2026-08-01"):
    return {
        "evidence_id": evidence_id,
        "sale_date": sold_date,
        "sale_price": price,
        "currency": "USD",
    }


def test_zero_mad_extreme_high_outlier_is_quarantined():
    sales = [
        _sale("a", 100),
        _sale("b", 100),
        _sale("c", 100),
        _sale("contamination", 1000),
    ]

    sample = valuation_sample(sales, "2026-08-15")

    assert [row["evidence_id"] for row in sample] == ["a", "b", "c"]
    estimate = estimate_market("CARD", sales, "2026-08-15")
    assert estimate.sample_size == 3
    assert estimate.fair_value == 100.0


def test_zero_mad_extreme_low_outlier_is_quarantined():
    sales = [
        _sale("a", 100),
        _sale("b", 100),
        _sale("c", 100),
        _sale("contamination", 10),
    ]

    sample = valuation_sample(sales, "2026-08-15")

    assert [row["evidence_id"] for row in sample] == ["a", "b", "c"]


def test_zero_mad_fallback_does_not_reject_nearby_legitimate_price():
    sales = [
        _sale("a", 100),
        _sale("b", 100),
        _sale("c", 100),
        _sale("nearby", 125),
    ]

    sample = valuation_sample(sales, "2026-08-15")

    assert [row["evidence_id"] for row in sample] == ["a", "b", "c", "nearby"]


def test_zero_mad_fallback_does_not_fire_on_sparse_three_sale_sample():
    sales = [
        _sale("a", 100),
        _sale("b", 100),
        _sale("suspicious_but_sparse", 1000),
    ]

    sample = valuation_sample(sales, "2026-08-15")

    assert [row["evidence_id"] for row in sample] == ["a", "b", "suspicious_but_sparse"]
