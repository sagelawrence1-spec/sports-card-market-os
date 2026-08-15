import csv
import tempfile
from pathlib import Path

from providers.ebay_product_research import EbayProductResearchProvider


def test_negative_product_research_money_fails_closed():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "research.csv"
        fields = ["Item Title", "Sold Price", "Sold Date", "Item ID", "Currency", "Shipping"]
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerow({
                "Item Title": "Valid comp",
                "Sold Price": "$100.00",
                "Sold Date": "2026-08-01",
                "Item ID": "123456789001",
                "Currency": "USD",
                "Shipping": "$0.00",
            })
            writer.writerow({
                "Item Title": "Negative sold price",
                "Sold Price": "-$125.00",
                "Sold Date": "2026-08-02",
                "Item ID": "123456789002",
                "Currency": "USD",
                "Shipping": "$0.00",
            })
            writer.writerow({
                "Item Title": "Negative shipping",
                "Sold Price": "$150.00",
                "Sold Date": "2026-08-03",
                "Item ID": "123456789003",
                "Currency": "USD",
                "Shipping": "-$5.00",
            })
            writer.writerow({
                "Item Title": "Accounting negative sold price",
                "Sold Price": "($175.00)",
                "Sold Date": "2026-08-04",
                "Item ID": "123456789004",
                "Currency": "USD",
                "Shipping": "$0.00",
            })

        result = EbayProductResearchProvider().load_csv(str(path), "negative money")

    assert len(result.records) == 1
    assert result.records[0].source_item_id == "123456789001"
    assert result.records[0].price == 100.0
    assert result.metadata["accepted_rows"] == 1
    assert result.metadata["rejected_rows"] == 3
    assert result.metadata["rejection_reasons"] == {
        "invalid_or_ambiguous_price": 2,
        "invalid_or_missing_shipping": 1,
    }
