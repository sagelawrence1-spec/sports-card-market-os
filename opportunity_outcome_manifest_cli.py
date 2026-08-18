"""CLI for producing authoritative forward outcome collection manifests."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from opportunity_outcome_manifest import build_authoritative_outcome_manifest


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
        description="Turn immutable Opportunity decisions into a complete forward eBay Product Research collection queue."
    )
    parser.add_argument("--jobs", required=True, help="JSON array of packet + entry_collection jobs, or -")
    parser.add_argument("--as-of", required=True, help="Timezone-aware cutoff used to determine horizon maturity")
    parser.add_argument("-o", "--output", default="-", help="Output manifest JSON path, or -")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        jobs = _read_json(args.jobs)
        if not isinstance(jobs, list):
            raise ValueError("jobs JSON must be an array")
        artifact = build_authoritative_outcome_manifest(jobs, as_of=args.as_of)
        _write_json(artifact, args.output)
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        sys.stderr.write(f"opportunity-outcome-manifest error: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
