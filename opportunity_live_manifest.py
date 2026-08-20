"""Build an authoritative Product Research work queue directly from the public Radar feed.

This is an operational bridge, not a new scoring path. It validates the tangible
public Radar candidates against the canonical research asset registry, reconstructs
the minimal internal Radar scan contract, then reuses the existing repricing-plan and
collection-manifest builders.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_repricing_manifest import build_collection_manifest
from opportunity_repricing_plan import build_repricing_plan

PUBLIC_SCHEMA = "opportunity-radar-public.v1"
SCHEMA = "opportunity-live-research-manifest.v1"


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


def _parse_time(value: Any, *, field: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _to_internal_scan(public_radar: Mapping[str, Any], assets: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    if public_radar.get("schema") != PUBLIC_SCHEMA:
        raise ValueError("unsupported public Radar schema")
    generated = _parse_time(public_radar.get("generated_at", ""), field="generated_at")
    raw_candidates = public_radar.get("candidates")
    if not isinstance(raw_candidates, list):
        raise ValueError("public Radar candidates must be a list")

    candidates: list[dict[str, Any]] = []
    seen_players: set[str] = set()
    seen_cards: set[str] = set()
    for rank, row in enumerate(raw_candidates, start=1):
        if not isinstance(row, Mapping):
            raise ValueError("public Radar candidate must be an object")
        player_id = str(row.get("player_id", "")).strip()
        player = str(row.get("player", "")).strip()
        card_id = str(row.get("card_id", "")).strip()
        card_label = str(row.get("card", "")).strip()
        if not player_id or not player or not card_id or not card_label:
            raise ValueError("public Radar candidate requires player_id, player, card_id, and card")
        if player_id in seen_players:
            raise ValueError(f"duplicate public Radar player_id: {player_id}")
        if card_id in seen_cards:
            raise ValueError(f"duplicate public Radar card_id: {card_id}")
        seen_players.add(player_id)
        seen_cards.add(card_id)

        asset = assets.get(card_id)
        if not isinstance(asset, Mapping):
            raise ValueError(f"public Radar card has no canonical research asset: {card_id}")
        asset_player = str(asset.get("player", "")).strip()
        if asset_player.casefold() != player.casefold():
            raise ValueError(f"canonical asset player mismatch for {card_id}")

        observed = _parse_time(row.get("observed_at", ""), field="observed_at")
        if observed > generated:
            raise ValueError(f"public Radar observation occurs after generated_at: {player_id}")
        lag_minutes = (generated - observed).total_seconds() / 60.0

        candidates.append({
            "rank": rank,
            "player_id": player_id,
            "player": player,
            "thesis_type": row.get("thesis_type"),
            "stage": row.get("stage"),
            "decision": row.get("decision"),
            "observed_at": observed.isoformat(),
            "observation_to_scan_lag_minutes": lag_minutes,
            "cards": [{"card_id": card_id, "label": card_label, "priority": 1}],
        })

    return {
        "schema": "opportunity-radar-scan.v1",
        "generated_at": generated.isoformat(),
        "input_count": len(candidates),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def build_live_research_manifest(
    public_radar: Mapping[str, Any],
    *,
    assets: Mapping[str, Mapping[str, Any]],
    as_of: str | None = None,
    max_requests: int = 10,
    include_p2: bool = False,
) -> dict[str, Any]:
    """Turn the tangible Radar queue into the exact Product Research export queue."""
    scan = _to_internal_scan(public_radar, assets)
    plan = build_repricing_plan(scan, as_of=as_of)
    manifest = build_collection_manifest(plan, max_requests=max_requests, include_p2=include_p2)
    return {
        "schema": SCHEMA,
        "source_public_schema": PUBLIC_SCHEMA,
        "source_generated_at": public_radar.get("generated_at"),
        "candidate_count": len(scan["candidates"]),
        "canonical_asset_count": len(assets),
        "repricing_plan": plan,
        "collection_manifest": manifest,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the eBay Product Research queue directly from public Opportunity Radar.")
    parser.add_argument("--radar", required=True, help="public opportunity-radar.json path, or -")
    parser.add_argument("--assets", default="config/opportunity_assets.json", help="canonical Opportunity asset registry")
    parser.add_argument("--as-of", help="optional timezone-aware repricing cutoff; defaults to Radar generated_at")
    parser.add_argument("--max-requests", type=int, default=10)
    parser.add_argument("--include-p2", action="store_true")
    parser.add_argument("-o", "--output", default="-", help="output JSON path, or -")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        radar = _read_json(args.radar)
        assets = _read_json(args.assets)
        if not isinstance(radar, dict):
            raise ValueError("Radar JSON must be an object")
        if not isinstance(assets, dict):
            raise ValueError("assets JSON must be an object")
        result = build_live_research_manifest(
            radar,
            assets=assets,
            as_of=args.as_of,
            max_requests=args.max_requests,
            include_p2=args.include_p2,
        )
        _write_json(result, args.output)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        sys.stderr.write(f"opportunity-live-manifest error: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
