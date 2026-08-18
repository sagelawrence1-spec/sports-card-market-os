"""CLI for producing a prioritized Product Research collection manifest."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from opportunity_repricing_manifest import build_collection_manifest


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
        description="Turn an Opportunity repricing plan into a prioritized eBay Product Research collection queue."
    )
    parser.add_argument("--plan", required=True, help="opportunity-repricing-plan.v1 JSON path, or -")
    parser.add_argument("--max-requests", type=int, default=10, help="Maximum collection requests to emit")
    parser.add_argument("--include-p2", action="store_true", help="Include lower-urgency P2 requests")
    parser.add_argument("-o", "--output", default="-", help="Output manifest JSON path, or -")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        plan = _read_json(args.plan)
        if not isinstance(plan, dict):
            raise ValueError("plan JSON must be an object")
        artifact = build_collection_manifest(
            plan,
            max_requests=args.max_requests,
            include_p2=args.include_p2,
        )
        _write_json(artifact, args.output)
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        sys.stderr.write(f"opportunity-repricing-manifest error: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
