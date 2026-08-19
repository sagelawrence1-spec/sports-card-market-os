import csv

import pytest

from opportunity_outcome_collection import grade_authoritative_market_outcome
from opportunity_outcomes import OpportunityOutcomePolicy


def _packet():
    return {
        "schema": "opportunity-decision-packet.v1",
        "player_id": "player-1",
        "card": {"card_id": "card-10", "label": "2026 Topps Chrome Player One #10"},
        "catalyst_at": "2026-08-10T12:00:00+00:00",
        "as_of": "2026-08-18T10:00:00+00:00",
        "decision": "START_POSITION",
        "actionable": True,
    }


def _entry_collection():
    return {
        "schema": "opportunity-repricing-collection.v1",
        "player_id": "player-1",
        "card_id": "card-10",
        "verification": {
            "verified": True,
            "post_median": 100.0,
            "catalyst_at": "2026-08-10T12:00:00+00:00",
            "as_of": "2026-08-18T10:00:00+00:00",
        },
    }


def _asset():
    return {
        "card_id": "card-10",
        "player": "Player One",
        "year": 2026,
        "manufacturer": "Topps",
        "set_name": "Topps Chrome",
        "card_number": "10",
        "parallel": "base",
        "autograph": 0,
    }


def _row(item_id, sold_date, price, title="2026 Topps Chrome Player One #10"):
    return {
        "Title": title,
        "Sold Price": f"${price}",
        "Sold Date": sold_date,
        "Item ID": str(item_id),
        "Currency": "USD",
    }


def _write(tmp_path, rows):
    path = tmp_path / "forward.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Title", "Sold Price", "Sold Date", "Item ID", "Currency"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_grades_from_authoritative_forward_median_not_caller_price(tmp_path):
    rows = [
        _row(1, "2026-09-17", 999),  # exact 30-day horizon day: ambiguous, excluded
        _row(2, "2026-09-18", 120),
        _row(3, "2026-09-19", 130),
        _row(4, "2026-09-20", 140),
        _row(5, "2026-09-21", 999),  # as_of day: ambiguous, excluded
        _row(6, "2026-09-19", 1000, "2026 Topps Chrome Player One #11"),
    ]
    result = grade_authoritative_market_outcome(
        _packet(),
        _entry_collection(),
        asset=_asset(),
        csv_path=_write(tmp_path, rows),
        as_of="2026-09-21T18:00:00+00:00",
    )

    assert result["schema"] == "opportunity-authoritative-outcome.v1"
    assert result["graded"] is True
    assert result["forward_count"] == 3
    assert result["forward_median"] == 130.0
    assert result["matching"]["excluded_horizon_day"] == 1
    assert result["matching"]["excluded_as_of_day"] == 1
    assert result["matching"]["rejected"] == 1
    assert result["outcome"]["entry_price"] == 100.0
    assert result["outcome"]["realized_price"] == 130.0
    assert result["outcome"]["net_return"] == pytest.approx(0.30)
    assert result["outcome"]["grade"] == "A"


def test_forward_evidence_identity_preserves_multi_quantity_sales_on_distinct_days(tmp_path):
    rows = [
        _row(1234567890, "2026-09-18", 120),
        _row(1234567890, "2026-09-19", 130),
        _row(1234567890, "2026-09-20", 140),
    ]
    result = grade_authoritative_market_outcome(
        _packet(),
        _entry_collection(),
        asset=_asset(),
        csv_path=_write(tmp_path, rows),
        as_of="2026-09-21T18:00:00+00:00",
    )

    assert result["graded"] is True
    assert result["forward_count"] == 3
    assert len(set(result["evidence_ids"])) == 3
    assert result["evidence_ids"] == [
        "ebay_product_research:1234567890:2026-09-18",
        "ebay_product_research:1234567890:2026-09-19",
        "ebay_product_research:1234567890:2026-09-20",
    ]


def test_blocks_when_forward_authoritative_depth_is_thin(tmp_path):
    rows = [_row(1, "2026-09-18", 120), _row(2, "2026-09-19", 130)]
    result = grade_authoritative_market_outcome(
        _packet(),
        _entry_collection(),
        asset=_asset(),
        csv_path=_write(tmp_path, rows),
        as_of="2026-09-21T18:00:00+00:00",
    )
    assert result["graded"] is False
    assert result["blocking_reason"] == "insufficient_forward_authoritative_comps"
    assert result["forward_count"] == 2


def test_applies_costs_to_authoritative_forward_median(tmp_path):
    rows = [_row(1, "2026-09-18", 110), _row(2, "2026-09-19", 110), _row(3, "2026-09-20", 110)]
    result = grade_authoritative_market_outcome(
        _packet(),
        _entry_collection(),
        asset=_asset(),
        csv_path=_write(tmp_path, rows),
        as_of="2026-09-21T18:00:00+00:00",
        policy=OpportunityOutcomePolicy(exit_fee_rate=0.05, liquidity_haircut_rate=0.05),
    )
    assert result["outcome"]["net_realized_price"] == pytest.approx(99.275)
    assert result["outcome"]["hit"] is False


def test_rejects_mismatched_asset_or_premature_cutoff(tmp_path):
    asset = _asset()
    asset["card_id"] = "wrong"
    with pytest.raises(ValueError, match="asset card_id"):
        grade_authoritative_market_outcome(
            _packet(), _entry_collection(), asset=asset, csv_path=tmp_path / "missing.csv", as_of="2026-09-21T18:00:00+00:00"
        )

    with pytest.raises(ValueError, match="minimum decision horizon"):
        grade_authoritative_market_outcome(
            _packet(), _entry_collection(), asset=_asset(), csv_path=tmp_path / "missing.csv", as_of="2026-09-01T18:00:00+00:00"
        )
