"""Command-line bridge from Product Research exports to Opportunity repricing proof."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from opportunity_repricing_collection import collect_repricing_verification


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
        description="Verify Opportunity Radar repricing from an authoritative eBay Product Research CSV export."
    )
    parser.add_argument("--request", required=True, help="opportunity-repricing-plan.v1 card request JSON path")
    parser.add_argument("--asset", required=True, help="Canonical card asset JSON path")
    parser.add_argument("--csv", required=True, help="eBay Product Research CSV export path")
    parser.add_argument("-o", "--output", default="-", help="Output opportunity-repricing-collection.v1 JSON path, or -")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        request = _read_json(args.request)
        asset = _read_json(args.asset)
        if not isinstance(request, dict):
            raise ValueError("request JSON must be an object")
        if not isinstance(asset, dict):
            raise ValueError("asset JSON must be an object")
        artifact = collect_repricing_verification(request, asset=asset, csv_path=args.csv)
        _write_json(artifact, args.output)
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        sys.stderr.write(f"opportunity-repricing error: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
