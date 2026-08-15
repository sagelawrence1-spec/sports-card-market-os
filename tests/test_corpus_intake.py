from corpus_intake import CorpusIntakePolicy, sanitize_product_research_rows


def test_sanitizer_removes_sensitive_fields_and_preserves_core_evidence():
    result = sanitize_product_research_rows([
        {
            "Item ID": "v1|123456789012|0",
            "Title": "2017 Topps Chrome Aaron Judge #169 PSA 10",
            "Sold Price": "$250.00",
            "Sold Date": "2026-08-01",
            "Currency": "USD",
            "Seller Username": "private-seller",
            "Buyer Name": "Private Buyer",
        }
    ])
    assert result["ready"] is True
    assert result["accepted_rows"] == 1
    row = result["accepted"][0]
    assert row["item_id"] == "123456789012"
    assert row["sold_price"] == 250.0
    assert row["sold_date"] == "2026-08-01"
    assert "seller_username" not in row
    assert "buyer_name" not in row


def test_ambiguous_price_range_fails_closed():
    result = sanitize_product_research_rows([
        {
            "Item ID": "123456789012",
            "Title": "Shohei Ohtani PSA 10",
            "Sold Price": "$100 - $150",
            "Sold Date": "2026-08-01",
            "Currency": "USD",
        }
    ])
    assert result["accepted_rows"] == 0
    assert result["rejected_rows"] == 1
    assert "invalid_or_ambiguous_price" in result["rejected"][0]["reasons"]


def test_non_usd_rows_fail_closed_by_default():
    result = sanitize_product_research_rows([
        {
            "Item ID": "123456789012",
            "Title": "Shohei Ohtani PSA 10",
            "Sold Price": "125.00",
            "Sold Date": "2026-08-01",
            "Currency": "CAD",
        }
    ])
    assert result["accepted_rows"] == 0
    assert "non_usd_currency" in result["rejected"][0]["reasons"]


def test_missing_currency_is_not_silently_assumed_usd():
    result = sanitize_product_research_rows([
        {
            "Item ID": "123456789012",
            "Title": "Shohei Ohtani PSA 10",
            "Sold Price": "125.00",
            "Sold Date": "2026-08-01",
        }
    ])
    assert result["accepted_rows"] == 0
    assert "missing_currency" in result["rejected"][0]["reasons"]


def test_dollar_price_can_supply_usd_when_currency_column_is_absent():
    result = sanitize_product_research_rows([
        {
            "Item ID": "123456789012",
            "Title": "Shohei Ohtani PSA 10",
            "Sold Price": "$125.00",
            "Sold Date": "2026-08-01",
        }
    ])
    assert result["accepted_rows"] == 1
    assert result["accepted"][0]["currency"] == "USD"


def test_common_sold_date_format_is_normalized_to_iso():
    result = sanitize_product_research_rows([
        {
            "Item ID": "123456789012",
            "Title": "Shohei Ohtani PSA 10",
            "Sold Price": "$125.00",
            "Sold Date": "08/01/2026",
            "Currency": "USD",
        }
    ])
    assert result["accepted_rows"] == 1
    assert result["accepted"][0]["sold_date"] == "2026-08-01"


def test_malformed_sold_date_fails_closed():
    result = sanitize_product_research_rows([
        {
            "Item ID": "123456789012",
            "Title": "Shohei Ohtani PSA 10",
            "Sold Price": "$125.00",
            "Sold Date": "not-a-date",
            "Currency": "USD",
        }
    ])
    assert result["accepted_rows"] == 0
    assert "invalid_sold_date" in result["rejected"][0]["reasons"]


def test_duplicate_item_ids_are_deduped_deterministically():
    row = {
        "Item ID": "123456789012",
        "Title": "Shohei Ohtani PSA 10",
        "Sold Price": "$125.00",
        "Sold Date": "2026-08-01",
        "Currency": "USD",
    }
    result = sanitize_product_research_rows([row, dict(row)])
    assert result["accepted_rows"] == 1
    assert result["duplicates"] == 1


def test_missing_core_fields_block_export_readiness():
    result = sanitize_product_research_rows(
        [
            {
                "Item ID": "123456789012",
                "Sold Price": "$125.00",
                "Sold Date": "2026-08-01",
                "Currency": "USD",
            }
        ],
        policy=CorpusIntakePolicy(max_missing_required_share=0.0),
    )
    assert result["ready"] is False
    assert "required_field_loss_exceeds_policy" in result["blockers"]


def test_corpus_hash_is_stable_for_identical_input():
    rows = [
        {
            "Item ID": "123456789012",
            "Title": "Shohei Ohtani PSA 10",
            "Sold Price": "$125.00",
            "Sold Date": "2026-08-01",
            "Currency": "USD",
        }
    ]
    first = sanitize_product_research_rows(rows)
    second = sanitize_product_research_rows(rows)
    assert first["corpus_sha256"] == second["corpus_sha256"]
