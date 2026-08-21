"""Auditable receipt for an authoritative eBay Product Research export."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from providers.ebay_product_research import EbayProductResearchProvider

SCHEMA = "product-research-receipt.v1"


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

    columns = metadata.get("columns") or {}
    if rows and not columns.get("quantity"):
        raise ValueError(
            "Product Research authoritative receipt requires an explicit quantity column"
        )

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
