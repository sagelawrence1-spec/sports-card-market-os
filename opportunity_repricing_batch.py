"""Batch authoritative repricing collection from a round-trippable manifest."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from opportunity_repricing_collection import collect_repricing_verification


def collect_manifest_batch(
    manifest: Mapping[str, Any],
    *,
    assets: Mapping[str, Mapping[str, Any]],
    export_dir: str | Path,
) -> dict[str, Any]:
    if manifest.get("schema") != "opportunity-repricing-collection-manifest.v1":
        raise ValueError("unsupported collection manifest schema")
    items = manifest.get("items")
    if not isinstance(items, list):
        raise ValueError("collection manifest items must be a list")

    root = Path(export_dir)
    results: list[dict[str, Any]] = []
    complete = 0
    missing = 0
    failed = 0

    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("collection manifest item must be an object")
        card_id = str(item.get("card_id", "")).strip()
        filename = str(item.get("expected_export_filename", "")).strip()
        request = item.get("repricing_request")
        if not card_id or not filename or not isinstance(request, Mapping):
            raise ValueError("manifest item requires card_id, expected_export_filename, and repricing_request")
        if str(request.get("card_id", "")).strip() != card_id:
            raise ValueError("manifest item card_id must match repricing_request")

        asset = assets.get(card_id)
        csv_path = root / filename
        if asset is None:
            failed += 1
            results.append({"card_id": card_id, "status": "MISSING_ASSET", "csv_path": str(csv_path)})
            continue
        if not csv_path.is_file():
            missing += 1
            results.append({"card_id": card_id, "status": "MISSING_EXPORT", "csv_path": str(csv_path)})
            continue

        try:
            artifact = collect_repricing_verification(request, asset=asset, csv_path=csv_path)
        except (OSError, KeyError, TypeError, ValueError) as exc:
            failed += 1
            results.append(
                {"card_id": card_id, "status": "COLLECTION_FAILED", "csv_path": str(csv_path), "error": str(exc)}
            )
            continue

        complete += 1
        results.append({"card_id": card_id, "status": "COLLECTED", "csv_path": str(csv_path), "artifact": artifact})

    return {
        "schema": "opportunity-repricing-batch.v1",
        "source_manifest_generated_at": manifest.get("source_scan_generated_at"),
        "requested_count": len(items),
        "collected_count": complete,
        "missing_export_count": missing,
        "failed_count": failed,
        "ready": complete == len(items) and failed == 0 and missing == 0,
        "results": results,
    }
