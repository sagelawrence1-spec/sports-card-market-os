"""Auditable receipt for an authoritative eBay Product Research export."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from providers.ebay_product_research import EbayProductResearchProvider

SCHEMA = "product-research-receipt.v1"


def _validate_authoritative_records(records) -> None:
    for record in records:
        if record.provider != "ebay_product_research":
            raise ValueError(
                f"Product Research receipt contains non-authoritative provider: {record.provider}"
            )
        if record.record_type != "sold":
            raise ValueError(
                f"Product Research receipt contains non-sold evidence: {record.record_type}"
            )
        if record.currency != "USD":
            raise ValueError(
                f"Product Research receipt contains non-USD evidence: {record.currency}"
            )
        if not record.source_item_id or not str(record.source_item_id).isdigit():
            raise ValueError("Product Research receipt contains invalid stable item identity")
        if not record.event_date:
            raise ValueError("Product Research receipt contains sold evidence without an event date")
        if record.price is None or float(record.price) <= 0:
            raise ValueError("Product Research receipt contains non-positive landed price evidence")
        if record.payload.get("price_basis") != "sold_price_plus_shipping":
            raise ValueError("Product Research receipt contains inconsistent landed-price basis")


def build_receipt(path: str | Path, *, query: str = "") -> dict[str, Any]:
    source = Path(path)
    raw = source.read_bytes()
    result = EbayProductResearchProvider().load_csv(str(source), query=query)
    metadata = result.metadata

    rows = int(metadata.get("rows", 0))
    accepted = int(metadata.get("accepted_rows", len(result.records)))
    deduplicated = int(metadata.get("deduplicated_rows", 0))
    rejected = int(metadata.get("rejected_rows", 0))
    accounted = accepted + deduplicated + rejected
    if accounted != rows:
        raise ValueError(
            f"Product Research row accounting mismatch: rows={rows} accounted={accounted}"
        )
    if accepted != len(result.records):
        raise ValueError(
            f"Product Research accepted-row mismatch: metadata={accepted} records={len(result.records)}"
        )

    columns = metadata.get("columns") or {}
    if rows and not columns.get("quantity"):
        raise ValueError(
            "Product Research authoritative receipt requires an explicit quantity column"
        )

    _validate_authoritative_records(result.records)

    accepted_evidence_ids = [
        f"{record.provider}:{record.source_item_id}:{record.event_date}"
        for record in result.records
    ]
    if len(set(accepted_evidence_ids)) != len(accepted_evidence_ids):
        raise ValueError("Product Research authoritative receipt contains duplicate evidence IDs")

    return {
        "schema": SCHEMA,
        "source": {
            "filename": source.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        },
        "provider": result.provider,
        "query": result.query,
        "price_basis": metadata.get("price_basis"),
        "quantity_basis": "explicit_exported_quantity",
        "rows": {
            "raw": rows,
            "accepted": accepted,
            "deduplicated": deduplicated,
            "rejected": rejected,
            "accounted": accounted,
        },
        "rejection_reasons": metadata.get("rejection_reasons", {}),
        "accepted_evidence_ids": accepted_evidence_ids,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fingerprint and audit an eBay Product Research CSV before downstream use."
    )
    parser.add_argument("csv_path")
    parser.add_argument("--query", default="")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)

    receipt = build_receipt(args.csv_path, query=args.query)
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output == "-":
        print(rendered, end="")
    else:
        Path(args.output).write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
