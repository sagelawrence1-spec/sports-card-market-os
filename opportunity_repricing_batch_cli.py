"""CLI for batch-processing authoritative Product Research exports from a manifest."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from opportunity_repricing_batch import collect_manifest_batch


def _read_json(path: str) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(payload: Any, path: str) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path == "-":
        sys.stdout.write(rendered)
    else:
        Path(path).write_text(rendered, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch-verify Product Research exports from a collection manifest.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--assets", required=True, help="JSON object keyed by canonical card_id")
    parser.add_argument("--export-dir", required=True)
    parser.add_argument("-o", "--output", default="-")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = _read_json(args.manifest)
        assets = _read_json(args.assets)
        if not isinstance(manifest, dict):
            raise ValueError("manifest JSON must be an object")
        if not isinstance(assets, dict):
            raise ValueError("assets JSON must be an object keyed by card_id")
        artifact = collect_manifest_batch(manifest, assets=assets, export_dir=args.export_dir)
        _write_json(artifact, args.output)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        sys.stderr.write(f"opportunity-repricing-batch error: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
