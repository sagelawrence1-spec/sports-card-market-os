from pathlib import Path

from providers.ebay_product_research import EbayProductResearchProvider


def test_accepts_official_ebay_report_header_vocabulary(tmp_path: Path):
    export = tmp_path / "ebay-report.csv"
    export.write_text(
        "Item Number,Item Title,Quantity,Sold For,Shipping And Handling,Sale Date,Selling Format\n"
        '123456789012,"2025 Elian Pena Bowman Chrome CPA-EP Autograph",1,$100.00,$5.00,08/19/2026,Auction\n',
        encoding="utf-8",
    )

    result = EbayProductResearchProvider().load_csv(str(export), query="Elian Pena")

    assert len(result.records) == 1
    record = result.records[0]
    assert record.source_item_id == "123456789012"
    assert record.price == 105.0
    assert record.event_date == "2026-08-19"
    assert record.payload["normalized_sold_price"] == 100.0
    assert record.payload["normalized_shipping"] == 5.0
    assert record.payload["normalized_listing_format"] == "Auction"
    assert record.payload["normalized_quantity"] == 1
    assert result.metadata["columns"]["id"] == "Item Number"
    assert result.metadata["columns"]["price"] == "Sold For"
    assert result.metadata["columns"]["shipping"] == "Shipping And Handling"
    assert result.metadata["columns"]["format"] == "Selling Format"
    assert result.metadata["columns"]["quantity"] == "Quantity"


def test_rejects_multi_unit_official_ebay_sale_from_single_card_comps(tmp_path: Path):
    export = tmp_path / "ebay-report.csv"
    export.write_text(
        "Item Number,Item Title,Quantity,Sold For,Shipping And Handling,Sale Date,Selling Format\n"
        '123456789012,"2025 Elian Pena Bowman Chrome CPA-EP Autograph",2,$180.00,$5.00,08/19/2026,Buy It Now\n',
        encoding="utf-8",
    )

    result = EbayProductResearchProvider().load_csv(str(export), query="Elian Pena")

    assert result.records == []
    assert result.metadata["accepted_rows"] == 0
    assert result.metadata["rejected_rows"] == 1
    assert result.metadata["rejection_reasons"] == {"multi_unit_sale": 1}


def test_rejects_malformed_quantity_when_official_quantity_column_is_present(tmp_path: Path):
    export = tmp_path / "ebay-report.csv"
    export.write_text(
        "Item Number,Item Title,Quantity,Sold For,Shipping And Handling,Sale Date,Selling Format\n"
        '123456789012,"2025 Elian Pena Bowman Chrome CPA-EP Autograph",N/A,$100.00,$5.00,08/19/2026,Auction\n',
        encoding="utf-8",
    )

    result = EbayProductResearchProvider().load_csv(str(export), query="Elian Pena")

    assert result.records == []
    assert result.metadata["accepted_rows"] == 0
    assert result.metadata["rejected_rows"] == 1
    assert result.metadata["rejection_reasons"] == {"invalid_or_missing_quantity": 1}
