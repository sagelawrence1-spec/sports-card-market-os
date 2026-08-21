from corpus_intake import sanitize_product_research_rows


def _row(**overrides):
    row = {
        "Item ID": "123456789012",
        "Title": "Shohei Ohtani PSA 10",
        "Sold Price": "$125.00",
        "Sold Date": "2026-08-01",
        "Currency": "USD",
        "Shipping": "$0.00",
    }
    row.update(overrides)
    return row


def test_explicit_item_id_does_not_rescue_non_ebay_url():
    result = sanitize_product_research_rows(
        [_row(URL="https://example.com/itm/123456789012")]
    )

    assert result["accepted_rows"] == 0
    assert "invalid_item_url" in result["rejected"][0]["reasons"]


def test_explicit_item_id_does_not_rescue_malformed_ebay_url():
    result = sanitize_product_research_rows(
        [_row(URL="https://www.ebay.com/sch/i.html?_nkw=ohtani")]
    )

    assert result["accepted_rows"] == 0
    assert "invalid_item_url" in result["rejected"][0]["reasons"]


def test_matching_ebay_item_url_remains_accepted():
    result = sanitize_product_research_rows(
        [_row(URL="https://www.ebay.com/itm/123456789012")]
    )

    assert result["accepted_rows"] == 1
    assert result["accepted"][0]["item_id"] == "123456789012"
