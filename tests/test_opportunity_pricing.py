from opportunity_pricing import OpportunityPriceComp, apply_verified_repricing, verify_repricing


def _comp(evidence_id: str, sold_at: str, price: float, card_id: str = "card-1", source_type: str = "EBAY_PRODUCT_RESEARCH") -> OpportunityPriceComp:
    return OpportunityPriceComp(evidence_id, card_id, sold_at, price, source_type)


def _evidence() -> list[OpportunityPriceComp]:
    return [
        _comp("pre-1", "2026-08-01T12:00:00+00:00", 95),
        _comp("pre-2", "2026-08-05T12:00:00+00:00", 100),
        _comp("pre-3", "2026-08-10T12:00:00+00:00", 105),
        _comp("post-1", "2026-08-16T12:00:00+00:00", 125),
        _comp("post-2", "2026-08-17T12:00:00+00:00", 130),
        _comp("post-3", "2026-08-18T12:00:00+00:00", 135),
    ]


def test_verifies_time_bounded_authoritative_repricing():
    result = verify_repricing(
        card_id="card-1",
        catalyst_at="2026-08-16T00:00:00+00:00",
        as_of="2026-08-19T00:00:00+00:00",
        comps=_evidence(),
    )
    assert result.verified is True
    assert result.pre_median == 100.0
    assert result.post_median == 130.0
    assert result.repricing_pct == 30.0
    assert result.pre_count == 3
    assert result.post_count == 3


def test_future_sales_do_not_leak_into_repricing():
    comps = _evidence() + [_comp("future", "2026-08-25T12:00:00+00:00", 500)]
    result = verify_repricing(
        card_id="card-1",
        catalyst_at="2026-08-16T00:00:00+00:00",
        as_of="2026-08-19T00:00:00+00:00",
        comps=comps,
    )
    assert result.verified is True
    assert result.post_median == 130.0
    assert "future" not in result.evidence_ids


def test_non_authoritative_and_wrong_card_sales_cannot_satisfy_depth():
    comps = _evidence()[:3] + [
        _comp("wrong-card-1", "2026-08-17T12:00:00+00:00", 130, card_id="card-2"),
        _comp("wrong-card-2", "2026-08-18T12:00:00+00:00", 135, card_id="card-2"),
        _comp("weak-source", "2026-08-17T12:00:00+00:00", 140, source_type="MARKETPLACE_SCREENSHOT"),
    ]
    result = verify_repricing(
        card_id="card-1",
        catalyst_at="2026-08-16T00:00:00+00:00",
        as_of="2026-08-19T00:00:00+00:00",
        comps=comps,
    )
    assert result.verified is False
    assert result.blocking_reason == "insufficient_post_catalyst_comps"


def test_duplicate_evidence_fails_closed():
    comps = _evidence() + [_comp("post-3", "2026-08-18T12:00:00+00:00", 135)]
    try:
        verify_repricing(
            card_id="card-1",
            catalyst_at="2026-08-16T00:00:00+00:00",
            as_of="2026-08-19T00:00:00+00:00",
            comps=comps,
        )
    except ValueError as exc:
        assert "duplicate pricing evidence_id" in str(exc)
    else:
        raise AssertionError("duplicate evidence must fail closed")


def test_successful_verification_upgrades_radar_payload():
    verification = verify_repricing(
        card_id="card-1",
        catalyst_at="2026-08-16T00:00:00+00:00",
        as_of="2026-08-19T00:00:00+00:00",
        comps=_evidence(),
    )
    payload = {"cards": [{"card_id": "card-1", "label": "Target card"}]}
    upgraded = apply_verified_repricing(payload, verification)
    assert upgraded["market_price_verified"] is True
    assert upgraded["market_repricing_pct"] == 30.0
    assert upgraded["pricing_verification"]["evidence_ids"] == verification.evidence_ids


def test_failed_verification_cannot_upgrade_radar_payload():
    verification = verify_repricing(
        card_id="card-1",
        catalyst_at="2026-08-16T00:00:00+00:00",
        as_of="2026-08-17T00:00:00+00:00",
        comps=_evidence()[:4],
    )
    upgraded = apply_verified_repricing(
        {"cards": [{"card_id": "card-1"}], "market_repricing_pct": 99}, verification
    )
    assert upgraded["market_price_verified"] is False
    assert "market_repricing_pct" not in upgraded
