"""Command-line runner for validated Opportunity Radar feeds."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from opportunity_feed import process_opportunity_feed


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
        description="Validate an opportunity-radar-feed.v1 payload and emit an opportunity-radar-scan.v1 artifact."
    )
    parser.add_argument("input", nargs="?", default="-", help="Input feed JSON path, or - for stdin")
    parser.add_argument("-o", "--output", default="-", help="Output scan JSON path, or - for stdout")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        feed = _read_json(args.input)
        if not isinstance(feed, dict):
            raise ValueError("feed JSON must be an object")
        artifact = process_opportunity_feed(feed)
        _write_json(artifact, args.output)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        sys.stderr.write(f"opportunity-feed error: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
