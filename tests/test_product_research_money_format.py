import csv
import tempfile
from pathlib import Path

from providers.ebay_product_research import EbayProductResearchProvider


def test_malformed_product_research_money_fails_closed():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "research.csv"
        fields = ["Item Title", "Sold Price", "Sold Date", "Item ID", "Currency", "Shipping"]
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerow({
                "Item Title": "Valid thousands comp",
                "Sold Price": "$1,234.56",
                "Sold Date": "2026-08-01",
                "Item ID": "123456789001",
                "Currency": "USD",
                "Shipping": "$5.00",
            })
            writer.writerow({
                "Item Title": "Embedded text",
                "Sold Price": "$12abc34",
                "Sold Date": "2026-08-02",
                "Item ID": "123456789002",
                "Currency": "USD",
                "Shipping": "$0.00",
            })
            writer.writerow({
                "Item Title": "Malformed thousands",
                "Sold Price": "$1,23.45",
                "Sold Date": "2026-08-03",
                "Item ID": "123456789003",
                "Currency": "USD",
                "Shipping": "$0.00",
            })
            writer.writerow({
                "Item Title": "Malformed shipping",
                "Sold Price": "$150.00",
                "Sold Date": "2026-08-04",
                "Item ID": "123456789004",
                "Currency": "USD",
                "Shipping": "$4..99",
            })
            writer.writerow({
                "Item Title": "Excess precision",
                "Sold Price": "$175.000",
                "Sold Date": "2026-08-05",
                "Item ID": "123456789005",
                "Currency": "USD",
                "Shipping": "$0.00",
            })

        result = EbayProductResearchProvider().load_csv(str(path), "strict money")

    assert len(result.records) == 1
    assert result.records[0].source_item_id == "123456789001"
    assert result.records[0].price == 1239.56
    assert result.metadata["accepted_rows"] == 1
    assert result.metadata["rejected_rows"] == 4
    assert result.metadata["rejection_reasons"] == {
        "invalid_or_ambiguous_price": 3,
        "invalid_or_missing_shipping": 1,
    }
