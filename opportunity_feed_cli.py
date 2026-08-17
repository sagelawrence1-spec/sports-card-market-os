"""Command-line runner for validated Opportunity Radar feeds."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from opportunity_attention import build_attention_brief
from opportunity_feed import process_opportunity_feed
from opportunity_scan_delta import build_radar_scan_delta


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
    parser.add_argument(
        "--previous-scan",
        help="Optional prior opportunity-radar-scan.v1 JSON used to compute scan-to-scan movement.",
    )
    parser.add_argument(
        "--delta-output",
        help="Where to write opportunity-radar-delta.v1 when --previous-scan is supplied.",
    )
    parser.add_argument(
        "--attention-output",
        help="Optional opportunity-radar-attention.v1 review queue; requires --previous-scan.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if bool(args.previous_scan) != bool(args.delta_output):
            raise ValueError("--previous-scan and --delta-output must be supplied together")
        if args.attention_output and not args.previous_scan:
            raise ValueError("--attention-output requires --previous-scan and --delta-output")
        feed = _read_json(args.input)
        if not isinstance(feed, dict):
            raise ValueError("feed JSON must be an object")
        artifact = process_opportunity_feed(feed)
        delta = None
        attention = None
        if args.previous_scan:
            previous_scan = _read_json(args.previous_scan)
            if not isinstance(previous_scan, dict):
                raise ValueError("previous scan JSON must be an object")
            delta = build_radar_scan_delta(previous_scan, artifact)
            if args.attention_output:
                attention = build_attention_brief(artifact, delta)
        _write_json(artifact, args.output)
        if delta is not None:
            _write_json(delta, args.delta_output)
        if attention is not None:
            _write_json(attention, args.attention_output)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        sys.stderr.write(f"opportunity-feed error: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
