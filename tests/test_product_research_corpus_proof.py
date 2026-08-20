import hashlib
from pathlib import Path

import pytest

import product_research_corpus_proof as bound_proof
from corpus_proof import ProofPolicy


def _candidates():
    return [
        {
            "card_id": "A",
            "player": "Shohei Ohtani",
            "sport": "Baseball",
            "year": "2025",
            "card_number": "1",
        },
        {
            "card_id": "B",
            "player": "Stephen Curry",
            "sport": "Basketball",
            "year": "2025",
            "card_number": "2",
        },
    ]


def _labels():
    return [
        {
            "evidence_id": "123456789012",
            "expected_status": "accepted",
            "expected_card_id": "A",
        },
        {
            "evidence_id": "123456789013",
            "expected_status": "accepted",
            "expected_card_id": "B",
        },
    ]


def _policy():
    return ProofPolicy(
        target_cards=2,
        min_labeled_rows=2,
        min_label_coverage=1.0,
        min_intake_retention=1.0,
        min_positive_recall=1.0,
        min_negative_label_share=None,
        max_review_rate=1.0,
        max_single_card_share=0.50,
        max_sport_share=0.50,
    )


def _write_export(path: Path, *, ohtani_title: str = "2025 Shohei Ohtani #1") -> None:
    path.write_text(
        "Item ID,Title,Sold Date,Sold Price,Currency,Shipping\n"
        f'123456789012,"{ohtani_title}",2026-08-01,$100.00,USD,$5.00\n'
        '123456789013,"2025 Stephen Curry #2",2026-08-02,$200.00,USD,$7.00\n'
    )


def test_authoritative_corpus_proof_is_bound_to_exact_export_bytes(tmp_path):
    export = tmp_path / "product-research.csv"
    _write_export(export)

    report = bound_proof.build_product_research_corpus_proof(
        export,
        _candidates(),
        _labels(),
        policy=_policy(),
        query="balanced proof export",
    )

    raw = export.read_bytes()
    expected_sha = hashlib.sha256(raw).hexdigest()
    authoritative = report["authoritative_source"]
    assert report["proof_ready"] is True
    assert authoritative["schema"] == "product-research-corpus-proof.v1"
    assert authoritative["binding"] == {
        "verified": True,
        "sha256": expected_sha,
        "size_bytes": len(raw),
        "raw_rows": 2,
        "provider": "ebay_product_research",
        "price_basis": "sold_price_plus_shipping",
    }
    assert authoritative["receipt"]["source"]["sha256"] == expected_sha
    assert authoritative["receipt"]["query"] == "balanced proof export"
    assert authoritative["receipt"]["rows"]["accepted"] == 2


def test_export_mutation_after_receipt_fails_closed(tmp_path, monkeypatch):
    export = tmp_path / "product-research.csv"
    _write_export(export)
    real_build_receipt = bound_proof.build_receipt

    def tampering_receipt(path, *, query=""):
        receipt = real_build_receipt(path, query=query)
        _write_export(Path(path), ohtani_title="2025 Shohei Ohtani changed #1")
        return receipt

    monkeypatch.setattr(bound_proof, "build_receipt", tampering_receipt)

    with pytest.raises(ValueError, match="changed after receipt"):
        bound_proof.build_product_research_corpus_proof(
            export,
            _candidates(),
            _labels(),
            policy=_policy(),
        )


def test_receipt_and_proof_row_accounting_must_match(tmp_path, monkeypatch):
    export = tmp_path / "product-research.csv"
    _write_export(export)
    real_build_receipt = bound_proof.build_receipt

    def bad_count_receipt(path, *, query=""):
        receipt = real_build_receipt(path, query=query)
        receipt["rows"]["raw"] = 3
        return receipt

    monkeypatch.setattr(bound_proof, "build_receipt", bad_count_receipt)

    with pytest.raises(ValueError, match="receipt/proof row mismatch"):
        bound_proof.build_product_research_corpus_proof(
            export,
            _candidates(),
            _labels(),
            policy=_policy(),
        )


def test_non_authoritative_provider_or_price_basis_cannot_be_bound(tmp_path, monkeypatch):
    export = tmp_path / "product-research.csv"
    _write_export(export)
    real_build_receipt = bound_proof.build_receipt

    def wrong_provider(path, *, query=""):
        receipt = real_build_receipt(path, query=query)
        receipt["provider"] = "public_ebay"
        return receipt

    monkeypatch.setattr(bound_proof, "build_receipt", wrong_provider)
    with pytest.raises(ValueError, match="authoritative eBay Product Research provider"):
        bound_proof.build_product_research_corpus_proof(
            export,
            _candidates(),
            _labels(),
            policy=_policy(),
        )

    def wrong_basis(path, *, query=""):
        receipt = real_build_receipt(path, query=query)
        receipt["price_basis"] = "asking_price"
        return receipt

    monkeypatch.setattr(bound_proof, "build_receipt", wrong_basis)
    with pytest.raises(ValueError, match="sold-price-plus-shipping"):
        bound_proof.build_product_research_corpus_proof(
            export,
            _candidates(),
            _labels(),
            policy=_policy(),
        )
