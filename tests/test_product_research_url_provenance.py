import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from providers.ebay_product_research import EbayProductResearchProvider


def test_url_derived_identity_requires_ebay_host():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "research.csv"
        fields = ["Item Title", "Sold Price", "Sold Date", "Item URL", "Currency", "Shipping"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow({
                "Item Title": "Valid eBay URL identity",
                "Sold Price": "$125.00",
                "Sold Date": "2026-08-01",
                "Item URL": "https://www.ebay.com/itm/example-card/123456789012?hash=abc",
                "Currency": "USD",
                "Shipping": "$0.00",
            })
            writer.writerow({
                "Item Title": "Spoofed non-eBay URL identity",
                "Sold Price": "$130.00",
                "Sold Date": "2026-08-02",
                "Item URL": "https://example.com/itm/example-card/999999999999",
                "Currency": "USD",
                "Shipping": "$0.00",
            })
            writer.writerow({
                "Item Title": "Credential-host spoof",
                "Sold Price": "$135.00",
                "Sold Date": "2026-08-03",
                "Item URL": "https://www.ebay.com@example.com/itm/888888888888",
                "Currency": "USD",
                "Shipping": "$0.00",
            })

        result = EbayProductResearchProvider().load_csv(str(path), "test")

    assert [record.source_item_id for record in result.records] == ["123456789012"]
    assert result.metadata["accepted_rows"] == 1
    assert result.metadata["rejected_rows"] == 2
    assert result.metadata["rejection_reasons"] == {"invalid_item_url": 2}


def test_explicit_item_id_does_not_override_spoofed_url_provenance():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "research.csv"
        fields = ["Item Title", "Sold Price", "Sold Date", "Item ID", "Item URL", "Currency", "Shipping"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow({
                "Item Title": "Valid explicit ID and eBay URL",
                "Sold Price": "$125.00",
                "Sold Date": "2026-08-01",
                "Item ID": "123456789012",
                "Item URL": "https://www.ebay.com/itm/example-card/123456789012",
                "Currency": "USD",
                "Shipping": "$0.00",
            })
            writer.writerow({
                "Item Title": "Explicit ID with non-eBay URL",
                "Sold Price": "$130.00",
                "Sold Date": "2026-08-02",
                "Item ID": "999999999999",
                "Item URL": "https://example.com/itm/example-card/999999999999",
                "Currency": "USD",
                "Shipping": "$0.00",
            })
            writer.writerow({
                "Item Title": "Explicit ID with credential-host spoof",
                "Sold Price": "$135.00",
                "Sold Date": "2026-08-03",
                "Item ID": "888888888888",
                "Item URL": "https://www.ebay.com@example.com/itm/888888888888",
                "Currency": "USD",
                "Shipping": "$0.00",
            })

        result = EbayProductResearchProvider().load_csv(str(path), "test")

    assert [record.source_item_id for record in result.records] == ["123456789012"]
    assert result.metadata["accepted_rows"] == 1
    assert result.metadata["rejected_rows"] == 2
    assert result.metadata["rejection_reasons"] == {"invalid_item_url": 2}