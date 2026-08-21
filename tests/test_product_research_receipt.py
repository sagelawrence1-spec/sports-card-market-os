import csv
import hashlib
import json

import pytest

import product_research_receipt as receipt_module
from product_research_receipt import build_receipt, main


def _write(path, rows):
    fields = ["Item Title", "Sold Price", "Shipping", "Sold Date", "Item ID", "Currency"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _row(*, item_id="123456789012", price="$100.00", sold_date="2026-08-01"):
    return {
        "Item Title": "2018 Topps Chrome Update Shohei Ohtani HMT1 PSA 10",
        "Sold Price": price,
        "Shipping": "$5.00",
        "Sold Date": sold_date,
        "Item ID": item_id,
        "Currency": "USD",
    }


def test_receipt_fingerprints_exact_source_and_reconciles_rows(tmp_path):
    path = tmp_path / "ohtani.csv"
    row = _row()
    _write(path, [row, row.copy(), _row(item_id="123456789013", price="-$50.00")])

    receipt = build_receipt(path, query="Ohtani HMT1 PSA 10")
    raw = path.read_bytes()

    assert receipt["schema"] == "product-research-receipt.v1"
    assert receipt["source"]["filename"] == "ohtani.csv"
    assert receipt["source"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert receipt["source"]["size_bytes"] == len(raw)
    assert receipt["price_basis"] == "sold_price_plus_shipping"
    assert receipt["rows"] == {
        "raw": 3,
        "accepted": 1,
        "deduplicated": 1,
        "rejected": 1,
        "accounted": 3,
    }
    assert receipt["rejection_reasons"] == {"invalid_or_ambiguous_price": 1}
    assert receipt["accepted_evidence_ids"] == [
        "ebay_product_research:123456789012:2026-08-01"
    ]


def test_receipt_hash_changes_when_raw_export_changes(tmp_path):
    path = tmp_path / "sold.csv"
    _write(path, [_row()])
    first = build_receipt(path)

    _write(path, [_row(price="$101.00")])
    second = build_receipt(path)

    assert first["source"]["sha256"] != second["source"]["sha256"]


def test_receipt_fails_closed_on_row_accounting_drift(tmp_path, monkeypatch):
    path = tmp_path / "sold.csv"
    _write(path, [_row()])

    original = receipt_module.EbayProductResearchProvider.load_csv

    def broken(self, path, query=""):
        result = original(self, path, query=query)
        result.metadata["accepted_rows"] = 0
        return result

    monkeypatch.setattr(receipt_module.EbayProductResearchProvider, "load_csv", broken)
    with pytest.raises(ValueError, match="row accounting mismatch"):
        build_receipt(path)


def test_receipt_preserves_distinct_sale_dates_for_same_item_id(tmp_path):
    path = tmp_path / "sold.csv"
    _write(
        path,
        [
            _row(item_id="123456789012", sold_date="2026-08-01", price="$100.00"),
            _row(item_id="123456789012", sold_date="2026-08-02", price="$105.00"),
        ],
    )

    receipt = build_receipt(path)

    assert receipt["rows"] == {
        "raw": 2,
        "accepted": 2,
        "deduplicated": 0,
        "rejected": 0,
        "accounted": 2,
    }
    assert receipt["accepted_evidence_ids"] == [
        "ebay_product_research:123456789012:2026-08-01",
        "ebay_product_research:123456789012:2026-08-02",
    ]


def test_receipt_fails_closed_on_duplicate_composite_evidence_id(tmp_path, monkeypatch):
    path = tmp_path / "sold.csv"
    _write(path, [_row()])

    original = receipt_module.EbayProductResearchProvider.load_csv

    def broken(self, path, query=""):
        result = original(self, path, query=query)
        result.records.append(result.records[0])
        result.metadata["accepted_rows"] = 2
        result.metadata["rows"] = 2
        return result

    monkeypatch.setattr(receipt_module.EbayProductResearchProvider, "load_csv", broken)
    with pytest.raises(ValueError, match="duplicate evidence IDs"):
        build_receipt(path)


def test_cli_writes_json_receipt(tmp_path):
    source = tmp_path / "sold.csv"
    output = tmp_path / "receipt.json"
    _write(source, [_row()])

    assert main([str(source), "--query", "Ohtani", "--output", str(output)]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["query"] == "Ohtani"
    assert payload["rows"]["accepted"] == 1
    assert payload["source"]["sha256"]