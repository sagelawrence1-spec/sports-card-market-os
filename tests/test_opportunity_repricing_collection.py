import csv

import pytest

from opportunity_repricing_collection import collect_repricing_verification


def _request():
    return {
        "player_id": "player-1",
        "card_id": "card-10",
        "source_type": "EBAY_PRODUCT_RESEARCH",
        "catalyst_at": "2026-08-10T12:00:00+00:00",
        "as_of": "2026-08-18T10:00:00+00:00",
        "pre_start": "2026-07-11T12:00:00+00:00",
        "post_window_end": "2026-08-17T12:00:00+00:00",
        "min_pre_comps": 3,
        "min_post_comps": 3,
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


def _write_csv(tmp_path, rows):
    path = tmp_path / "research.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Title", "Sold Price", "Sold Date", "Item ID", "Currency"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def _row(item_id, sold_date, price, title="2026 Topps Chrome Player One #10"):
    return {
        "Title": title,
        "Sold Price": f"${price}",
        "Sold Date": sold_date,
        "Item ID": str(item_id),
        "Currency": "USD",
    }


def test_collection_entity_matches_and_verifies_repricing_without_boundary_day_leakage(tmp_path):
    rows = [
        _row(1, "2026-08-01", 100),
        _row(2, "2026-08-02", 110),
        _row(3, "2026-08-03", 120),
        _row(4, "2026-08-10", 999),
        _row(5, "2026-08-11", 130),
        _row(6, "2026-08-12", 140),
        _row(7, "2026-08-13", 150),
        _row(8, "2026-08-18", 999),
    ]
    result = collect_repricing_verification(_request(), asset=_asset(), csv_path=_write_csv(tmp_path, rows))

    assert result["schema"] == "opportunity-repricing-collection.v1"
    assert result["matching"] == {
        "accepted": 6,
        "manual_review": 0,
        "rejected": 0,
        "excluded_ambiguous_catalyst_day": 1,
        "excluded_ambiguous_as_of_day": 1,
    }
    verification = result["verification"]
    assert verification["verified"] is True
    assert verification["pre_count"] == 3
    assert verification["post_count"] == 3
    assert verification["pre_median"] == 110.0
    assert verification["post_median"] == 140.0
    assert verification["repricing_pct"] == 27.27


def test_collection_does_not_turn_wrong_card_rows_into_repricing_evidence(tmp_path):
    rows = [
        _row(1, "2026-08-01", 100),
        _row(2, "2026-08-02", 110),
        _row(3, "2026-08-03", 120),
        _row(4, "2026-08-11", 130, "2026 Topps Chrome Player One #11"),
        _row(5, "2026-08-12", 140, "2026 Topps Chrome Player One #11"),
        _row(6, "2026-08-13", 150, "2026 Topps Chrome Player One #11"),
    ]
    result = collect_repricing_verification(_request(), asset=_asset(), csv_path=_write_csv(tmp_path, rows))

    assert result["matching"]["rejected"] == 3
    assert result["verification"]["verified"] is False
    assert result["verification"]["blocking_reason"] == "insufficient_post_catalyst_comps"


def test_collection_requires_authoritative_request_source(tmp_path):
    request = _request()
    request["source_type"] = "OTHER"
    with pytest.raises(ValueError, match="EBAY_PRODUCT_RESEARCH"):
        collect_repricing_verification(request, asset=_asset(), csv_path=tmp_path / "missing.csv")
