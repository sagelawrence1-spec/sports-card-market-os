"""Execute the live Opportunity Engine research loop from authoritative exports.

This module intentionally composes existing hardened contracts instead of adding new
matching, repricing, or capital logic. One run fingerprints every supplied Product
Research export, executes the repricing batch, builds decision packets, and can
atomically persist READY decisions.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_decision_batch import build_opportunity_decision_batch
from opportunity_decision_persist import persist_opportunity_decision_batch
from opportunity_repricing_batch import collect_manifest_batch
from product_research_receipt import build_receipt

SCHEMA = "opportunity-research-run.v1"
MANIFEST_SCHEMA = "opportunity-repricing-collection-manifest.v1"


def _read_json(path: str) -> Any:
    if path == "-":
        return json.load(sys.stdin)
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(payload: Any, path: str) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path == "-":
        sys.stdout.write(rendered)
        return
    Path(path).write_text(rendered, encoding="utf-8")


def execute_opportunity_research_run(
    manifest: Mapping[str, Any],
    *,
    assets: Mapping[str, Mapping[str, Any]],
    observations: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    export_dir: str | Path,
    ledger_path: str | Path | None = None,
) -> dict[str, Any]:
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unsupported collection manifest schema")
    items = manifest.get("items")
    if not isinstance(items, list):
        raise ValueError("collection manifest items must be a list")

    root = Path(export_dir)
    receipts: list[dict[str, Any]] = []
    missing_receipts = 0
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("collection manifest item must be an object")
        card_id = str(item.get("card_id", "")).strip()
        filename = str(item.get("expected_export_filename", "")).strip()
        request = item.get("repricing_request")
        if not card_id or not filename or not isinstance(request, Mapping):
            raise ValueError("manifest item requires card_id, expected_export_filename, and repricing_request")
        csv_path = root / filename
        if not csv_path.is_file():
            missing_receipts += 1
            receipts.append({
                "card_id": card_id,
                "status": "MISSING_EXPORT",
                "csv_path": str(csv_path),
            })
            continue
        query = str(request.get("query", "") or request.get("search_query", ""))
        receipt = build_receipt(csv_path, query=query)
        receipts.append({
            "card_id": card_id,
            "status": "RECEIPT_READY",
            "csv_path": str(csv_path),
            "receipt": receipt,
        })

    collection_batch = collect_manifest_batch(manifest, assets=assets, export_dir=root)
    decision_batch = build_opportunity_decision_batch(collection_batch, observations=observations)
    persistence = None
    if ledger_path is not None:
        persistence = persist_opportunity_decision_batch(decision_batch, ledger_path=ledger_path)

    return {
        "schema": SCHEMA,
        "source_manifest_generated_at": manifest.get("source_scan_generated_at"),
        "requested_count": len(items),
        "receipt_ready_count": len(items) - missing_receipts,
        "missing_export_count": missing_receipts,
        "receipts": receipts,
        "collection": collection_batch,
        "decisions": decision_batch,
        "persistence": persistence,
        "complete": (
            missing_receipts == 0
            and bool(collection_batch.get("ready"))
            and bool(decision_batch.get("ready"))
            and (persistence is None or bool(persistence.get("complete")))
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run authoritative Opportunity research end-to-end: fingerprint exports, "
            "verify repricing, build decisions, and optionally persist them."
        )
    )
    parser.add_argument("--manifest", required=True, help="repricing collection manifest JSON")
    parser.add_argument("--assets", required=True, help="canonical assets JSON mapping card_id -> asset")
    parser.add_argument("--observations", required=True, help="Radar observations JSON list or object")
    parser.add_argument("--exports", required=True, help="directory containing expected Product Research CSVs")
    parser.add_argument("--ledger", help="optional SQLite decision ledger path")
    parser.add_argument("-o", "--output", default="-", help="output JSON path, or -")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = _read_json(args.manifest)
        assets = _read_json(args.assets)
        observations = _read_json(args.observations)
        if not isinstance(manifest, dict):
            raise ValueError("manifest JSON must be an object")
        if not isinstance(assets, dict):
            raise ValueError("assets JSON must be an object")
        if not isinstance(observations, (dict, list)):
            raise ValueError("observations JSON must be an object or list")
        result = execute_opportunity_research_run(
            manifest,
            assets=assets,
            observations=observations,
            export_dir=args.exports,
            ledger_path=args.ledger,
        )
        _write_json(result, args.output)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        sys.stderr.write(f"opportunity-research-run error: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
