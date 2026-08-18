"""CLI for turning repricing batch artifacts into reviewable decision packets."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from opportunity_decision_batch import build_opportunity_decision_batch


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
        description="Build reviewable Opportunity Engine decision packets from a repricing batch."
    )
    parser.add_argument("--batch", required=True, help="opportunity-repricing-batch.v1 JSON path")
    parser.add_argument("--observations", required=True, help="Sourced Radar observations JSON path")
    parser.add_argument("-o", "--output", default="-", help="Output opportunity-decision-batch.v1 path, or -")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        batch = _read_json(args.batch)
        observations = _read_json(args.observations)
        if not isinstance(batch, dict):
            raise ValueError("batch JSON must be an object")
        if not isinstance(observations, (dict, list)):
            raise ValueError("observations JSON must be an object or list")
        _write_json(build_opportunity_decision_batch(batch, observations=observations), args.output)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        sys.stderr.write(f"opportunity-decision-batch error: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
