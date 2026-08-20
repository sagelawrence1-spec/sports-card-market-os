from corpus_intake import CorpusIntakePolicy, sanitize_product_research_rows


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


def test_sanitizer_removes_sensitive_fields_and_preserves_landed_evidence():
    result = sanitize_product_research_rows([
        _row(
            **{
                "Title": "2017 Topps Chrome Aaron Judge #169 PSA 10",
                "Sold Price": "$250.00",
                "Shipping": "$7.50",
                "Seller Username": "private-seller",
                "Buyer Name": "Private Buyer",
            }
        )
    ])
    assert result["ready"] is True
    assert result["accepted_rows"] == 1
    row = result["accepted"][0]
    assert row["item_id"] == "123456789012"
    assert row["sold_price"] == 250.0
    assert row["shipping"] == 7.5
    assert row["landed_price"] == 257.5
    assert row["price_basis"] == "sold_price_plus_shipping"
    assert row["sold_date"] == "2026-08-01"
    assert "seller_username" not in row
    assert "buyer_name" not in row


def test_malformed_explicit_item_id_fails_closed_like_production_provider():
    result = sanitize_product_research_rows([_row(**{"Item ID": "row-1004"})])
    assert result["accepted_rows"] == 0
    assert "invalid_item_id" in result["rejected"][0]["reasons"]


def test_legacy_wrapped_explicit_item_id_is_not_silently_normalized():
    result = sanitize_product_research_rows([_row(**{"Item ID": "v1|123456789012|0"})])
    assert result["accepted_rows"] == 0
    assert "invalid_item_id" in result["rejected"][0]["reasons"]


def test_ebay_url_can_supply_stable_item_identity_when_required():
    result = sanitize_product_research_rows(
        [_row(**{"Item ID": "", "URL": "https://www.ebay.com/itm/123456789012"})],
        policy=CorpusIntakePolicy(require_item_id=True),
    )
    assert result["accepted_rows"] == 1
    assert result["accepted"][0]["item_id"] == "123456789012"


def test_non_ebay_url_cannot_supply_stable_item_identity():
    result = sanitize_product_research_rows(
        [_row(**{"Item ID": "", "URL": "https://example.com/itm/123456789012"})],
        policy=CorpusIntakePolicy(require_item_id=True),
    )
    assert result["accepted_rows"] == 0
    assert "missing_stable_item_id" in result["rejected"][0]["reasons"]


def test_conflicting_explicit_and_url_item_identity_fails_closed():
    result = sanitize_product_research_rows(
        [_row(**{"URL": "https://www.ebay.com/itm/999999999999"})],
        policy=CorpusIntakePolicy(require_item_id=True),
    )
    assert result["accepted_rows"] == 0
    assert "conflicting_item_id" in result["rejected"][0]["reasons"]


def test_ambiguous_price_range_fails_closed():
    result = sanitize_product_research_rows([_row(**{"Sold Price": "$100 - $150"})])
    assert result["accepted_rows"] == 0
    assert "invalid_or_ambiguous_price" in result["rejected"][0]["reasons"]


def test_malformed_money_is_not_recovered_by_digit_stripping():
    result = sanitize_product_research_rows([_row(**{"Sold Price": "$12abc34"})])
    assert result["accepted_rows"] == 0
    assert "invalid_or_ambiguous_price" in result["rejected"][0]["reasons"]


def test_negative_money_fails_closed():
    result = sanitize_product_research_rows([_row(**{"Sold Price": "-$125.00"})])
    assert result["accepted_rows"] == 0
    assert "invalid_or_ambiguous_price" in result["rejected"][0]["reasons"]


def test_non_usd_rows_fail_closed_by_default():
    result = sanitize_product_research_rows([_row(Currency="CAD", **{"Sold Price": "CAD $125.00"})])
    assert result["accepted_rows"] == 0
    assert "non_usd_currency" in result["rejected"][0]["reasons"]


def test_missing_currency_is_not_silently_assumed_usd():
    result = sanitize_product_research_rows([_row(Currency="", **{"Sold Price": "125.00"})])
    assert result["accepted_rows"] == 0
    assert "missing_currency" in result["rejected"][0]["reasons"]


def test_dollar_price_can_supply_usd_when_currency_column_is_absent():
    result = sanitize_product_research_rows([_row(Currency="")])
    assert result["accepted_rows"] == 1
    assert result["accepted"][0]["currency"] == "USD"


def test_qualified_foreign_dollar_is_not_assumed_usd():
    result = sanitize_product_research_rows([_row(Currency="", **{"Sold Price": "NZD $125.00"})])
    assert result["accepted_rows"] == 0
    assert "non_usd_currency" in result["rejected"][0]["reasons"]


def test_explicit_currency_conflict_fails_closed():
    result = sanitize_product_research_rows([_row(**{"Sold Price": "C$125.00"})])
    assert result["accepted_rows"] == 0
    assert "conflicting_currency_evidence" in result["rejected"][0]["reasons"]


def test_shipping_is_required_for_authoritative_corpus():
    result = sanitize_product_research_rows([_row(Shipping="")])
    assert result["accepted_rows"] == 0
    assert "missing_shipping" in result["rejected"][0]["reasons"]
    assert result["ready"] is False


def test_free_shipping_is_explicit_zero_shipping():
    result = sanitize_product_research_rows([_row(Shipping="Free shipping")])
    assert result["accepted_rows"] == 1
    assert result["accepted"][0]["shipping"] == 0.0
    assert result["accepted"][0]["landed_price"] == 125.0


def test_shipping_currency_conflict_fails_closed():
    result = sanitize_product_research_rows([_row(Shipping="C$5.00")])
    assert result["accepted_rows"] == 0
    assert "conflicting_shipping_currency" in result["rejected"][0]["reasons"]


def test_common_sold_date_format_is_normalized_to_iso():
    result = sanitize_product_research_rows([_row(**{"Sold Date": "08/01/2026"})])
    assert result["accepted_rows"] == 1
    assert result["accepted"][0]["sold_date"] == "2026-08-01"


def test_malformed_sold_date_fails_closed():
    result = sanitize_product_research_rows([_row(**{"Sold Date": "not-a-date"})])
    assert result["accepted_rows"] == 0
    assert "invalid_sold_date" in result["rejected"][0]["reasons"]


def test_duplicate_item_ids_same_day_are_deduped_deterministically():
    row = _row()
    result = sanitize_product_research_rows([row, dict(row)])
    assert result["accepted_rows"] == 1
    assert result["duplicates"] == 1
    assert result["conflicting_duplicates"] == 0
    assert result["ready"] is True


def test_conflicting_duplicate_item_id_same_day_fails_closed():
    first = _row()
    conflicting = {**first, "Sold Price": "$225.00"}
    result = sanitize_product_research_rows([first, conflicting])
    assert result["accepted_rows"] == 1
    assert result["rejected_rows"] == 1
    assert result["duplicates"] == 0
    assert result["conflicting_duplicates"] == 1
    assert result["ready"] is False
    assert "conflicting_duplicate_evidence" in result["rejected"][0]["reasons"]
    assert "conflicting_duplicate_evidence" in result["blockers"]


def test_same_item_id_on_different_days_preserves_distinct_sales():
    first = _row()
    second = {**first, "Sold Date": "2026-08-02"}
    result = sanitize_product_research_rows([first, second])
    assert result["accepted_rows"] == 2
    assert result["conflicting_duplicates"] == 0
    assert result["ready"] is True


def test_missing_core_fields_block_export_readiness():
    result = sanitize_product_research_rows(
        [
            {
                "Item ID": "123456789012",
                "Sold Price": "$125.00",
                "Sold Date": "2026-08-01",
                "Currency": "USD",
                "Shipping": "$0.00",
            }
        ],
        policy=CorpusIntakePolicy(max_missing_required_share=0.0),
    )
    assert result["ready"] is False
    assert "required_field_loss_exceeds_policy" in result["blockers"]


def test_corpus_hash_is_stable_for_identical_input():
    rows = [_row()]
    first = sanitize_product_research_rows(rows)
    second = sanitize_product_research_rows(rows)
    assert first["corpus_sha256"] == second["corpus_sha256"]