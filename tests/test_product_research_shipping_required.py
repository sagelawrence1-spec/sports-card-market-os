import csv
from pathlib import Path

import pytest

from providers.ebay_product_research import EbayProductResearchProvider


def _write_csv(path: Path, fieldnames, row):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)


def test_product_research_requires_shipping_column(tmp_path):
    path = tmp_path / "research.csv"
    _write_csv(
        path,
        ["Item Title", "Sold Price", "Sold Date", "Item ID", "Currency"],
        {
            "Item Title": "2025 Bowman Chrome Prospect Autograph CPA-TEST",
            "Sold Price": "$100.00",
            "Sold Date": "2026-08-18",
            "Item ID": "123456789012",
            "Currency": "USD",
        },
    )

    with pytest.raises(ValueError, match="title/price/date/shipping"):
        EbayProductResearchProvider().load_csv(str(path), "test card")


def test_product_research_uses_landed_price_when_shipping_is_explicit(tmp_path):
    path = tmp_path / "research.csv"
    _write_csv(
        path,
        ["Item Title", "Sold Price", "Sold Date", "Item ID", "Currency", "Shipping"],
        {
            "Item Title": "2025 Bowman Chrome Prospect Autograph CPA-TEST",
            "Sold Price": "$100.00",
            "Sold Date": "2026-08-18",
            "Item ID": "123456789012",
            "Currency": "USD",
            "Shipping": "$7.50",
        },
    )

    result = EbayProductResearchProvider().load_csv(str(path), "test card")

    assert len(result.records) == 1
    assert result.records[0].price == 107.50
    assert result.records[0].payload["normalized_sold_price"] == 100.0
    assert result.records[0].payload["normalized_shipping"] == 7.5
    assert result.records[0].payload["price_basis"] == "sold_price_plus_shipping"
    assert result.metadata["price_basis"] == "sold_price_plus_shipping"
