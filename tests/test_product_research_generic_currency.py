import csv
from pathlib import Path

from providers.ebay_product_research import EbayProductResearchProvider


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fields = ["Item Title", "Sold Price", "Sold Date", "Item ID", "Currency", "Shipping"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_explicit_usd_cannot_override_unlisted_foreign_currency_marker(tmp_path: Path) -> None:
    path = tmp_path / "research.csv"
    _write_csv(path, [{
        "Item Title": "Foreign currency comp",
        "Sold Price": "SGD $245.00",
        "Sold Date": "2026-08-20",
        "Item ID": "123456789012",
        "Currency": "USD",
        "Shipping": "$0.00",
    }])

    result = EbayProductResearchProvider().load_csv(str(path), "test")

    assert result.records == []
    assert result.metadata["rejection_reasons"] == {"conflicting_currency_evidence": 1}


def test_unlisted_foreign_currency_code_is_classified_non_usd(tmp_path: Path) -> None:
    path = tmp_path / "research.csv"
    _write_csv(path, [{
        "Item Title": "Foreign currency comp",
        "Sold Price": "SGD $245.00",
        "Sold Date": "2026-08-20",
        "Item ID": "123456789013",
        "Currency": "",
        "Shipping": "$0.00",
    }])

    result = EbayProductResearchProvider().load_csv(str(path), "test")

    assert result.records == []
    assert result.metadata["rejection_reasons"] == {"non_usd_currency": 1}


def test_explicit_usd_marker_without_dollar_symbol_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "research.csv"
    _write_csv(path, [{
        "Item Title": "Valid USD comp",
        "Sold Price": "USD 245.00",
        "Sold Date": "2026-08-20",
        "Item ID": "123456789014",
        "Currency": "",
        "Shipping": "USD 5.00",
    }])

    result = EbayProductResearchProvider().load_csv(str(path), "test")

    assert len(result.records) == 1
    assert result.records[0].currency == "USD"
    assert result.records[0].price == 250.0
    assert result.metadata["rejection_reasons"] == {}


def test_bare_dollar_amount_without_currency_provenance_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "research.csv"
    _write_csv(path, [{
        "Item Title": "Ambiguous dollar comp",
        "Sold Price": "$245.00",
        "Sold Date": "2026-08-20",
        "Item ID": "123456789015",
        "Currency": "",
        "Shipping": "$5.00",
    }])

    result = EbayProductResearchProvider().load_csv(str(path), "test")

    assert result.records == []
    assert result.metadata["rejection_reasons"] == {"missing_currency": 1}


def test_explicit_currency_column_authorizes_bare_dollar_amount(tmp_path: Path) -> None:
    path = tmp_path / "research.csv"
    _write_csv(path, [{
        "Item Title": "Explicit USD comp",
        "Sold Price": "$245.00",
        "Sold Date": "2026-08-20",
        "Item ID": "123456789016",
        "Currency": "USD",
        "Shipping": "$5.00",
    }])

    result = EbayProductResearchProvider().load_csv(str(path), "test")

    assert len(result.records) == 1
    assert result.records[0].currency == "USD"
    assert result.records[0].price == 250.0
    assert result.metadata["rejection_reasons"] == {}
