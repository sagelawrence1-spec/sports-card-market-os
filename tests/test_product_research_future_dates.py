import csv
from datetime import date, timedelta
from pathlib import Path

from providers.ebay_product_research import EbayProductResearchProvider


def _write_row(path: Path, sold_date: str):
    fieldnames = [
        "Item Title",
        "Sold Price",
        "Sold Date",
        "Item ID",
        "Currency",
        "Shipping",
        "Quantity",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "Item Title": "2025 Bowman Chrome Prospect Autograph CPA-TEST",
                "Sold Price": "$100.00",
                "Sold Date": sold_date,
                "Item ID": "123456789012",
                "Currency": "USD",
                "Shipping": "$5.00",
                "Quantity": "1",
            }
        )


def test_product_research_rejects_future_sold_dates(tmp_path):
    path = tmp_path / "research.csv"
    _write_row(path, (date.today() + timedelta(days=1)).isoformat())

    result = EbayProductResearchProvider().load_csv(str(path), "test card")

    assert result.records == []
    assert result.metadata["accepted_rows"] == 0
    assert result.metadata["rejected_rows"] == 1
    assert result.metadata["rejection_reasons"] == {"future_sold_date": 1}


def test_product_research_accepts_today_as_a_valid_sold_date(tmp_path):
    path = tmp_path / "research.csv"
    _write_row(path, date.today().isoformat())

    result = EbayProductResearchProvider().load_csv(str(path), "test card")

    assert len(result.records) == 1
    assert result.records[0].event_date == date.today().isoformat()
