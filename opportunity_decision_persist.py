"""Persist READY Opportunity Engine decision packets from a batch artifact."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_decision_ledger import OpportunityDecisionLedger

BATCH_SCHEMA = "opportunity-decision-batch.v1"
OUTPUT_SCHEMA = "opportunity-decision-persist.v1"


def persist_opportunity_decision_batch(
    batch: Mapping[str, Any], *, ledger_path: str | Path
) -> dict[str, Any]:
    if batch.get("schema") != BATCH_SCHEMA:
        raise ValueError("unsupported opportunity decision batch schema")
    raw_results = batch.get("results")
    if not isinstance(raw_results, list):
        raise ValueError("decision batch results must be a list")

    packets: list[Mapping[str, Any]] = []
    preserved: list[dict[str, Any]] = []
    for row in raw_results:
        if not isinstance(row, Mapping):
            raise ValueError("decision batch result must be an object")
        status = str(row.get("decision_status", "")).strip()
        if status == "READY":
            packet = row.get("packet")
            if not isinstance(packet, Mapping):
                raise ValueError("READY decision batch result requires packet")
            packets.append(packet)
            continue
        preserved.append(
            {
                "player_id": row.get("player_id"),
                "card_id": row.get("card_id"),
                "decision_status": status or "UNKNOWN",
                "blocking_reason": row.get("blocking_reason"),
                "error": row.get("error"),
            }
        )

    ledger = OpportunityDecisionLedger(ledger_path)
    decision_ids = ledger.persist_packets_atomic(packets)
    return {
        "schema": OUTPUT_SCHEMA,
        "requested_count": len(raw_results),
        "persisted_count": len(decision_ids),
        "preserved_non_ready_count": len(preserved),
        "decision_ids": list(decision_ids),
        "non_ready": preserved,
        "complete": len(decision_ids) + len(preserved) == len(raw_results),
    }


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Persist READY Opportunity Engine decisions atomically from a batch."
    )
    parser.add_argument("--batch", required=True, help="opportunity-decision-batch.v1 JSON path")
    parser.add_argument("--ledger", required=True, help="SQLite opportunity decision ledger path")
    parser.add_argument("-o", "--output", default="-", help="Output persistence receipt path, or -")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        batch = _read_json(args.batch)
        if not isinstance(batch, dict):
            raise ValueError("batch JSON must be an object")
        receipt = persist_opportunity_decision_batch(batch, ledger_path=args.ledger)
        _write_json(receipt, args.output)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        sys.stderr.write(f"opportunity-decision-persist error: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
