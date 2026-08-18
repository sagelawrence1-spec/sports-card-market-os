"""Build a reviewable Opportunity Engine decision packet from sourced observation + repricing proof."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_repricing_apply import apply_repricing_collection

_ACTIONABLE = {"START_POSITION", "ADD"}


def _aware(value: Any, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _decision_latency(observed_at: Any, as_of: Any) -> tuple[str, float, str]:
    observed = _aware(observed_at, field="observed_at")
    decision_at = _aware(as_of, field="as_of")
    lag_minutes = (decision_at - observed).total_seconds() / 60.0
    if lag_minutes < 0:
        raise ValueError("observed_at cannot be after decision as_of")
    if lag_minutes <= 360:
        bucket = "UNDER_6H"
    elif lag_minutes <= 1440:
        bucket = "6_TO_24H"
    else:
        bucket = "OVER_24H"
    return observed.isoformat(), lag_minutes, bucket


def build_opportunity_decision_packet(
    observation: Mapping[str, Any], collection: Mapping[str, Any]
) -> dict[str, Any]:
    """Return one durable, human-reviewable opportunity decision artifact."""
    update = apply_repricing_collection(observation, collection)

    player_id = str(observation.get("player_id", "")).strip()
    player = str(observation.get("player", "")).strip()
    headline = str(observation.get("headline", "")).strip()
    thesis = str(observation.get("thesis", "")).strip()
    why_now = str(observation.get("why_now", "")).strip()
    if not player_id or not player or not headline or not thesis or not why_now:
        raise ValueError("observation requires player identity, headline, thesis, and why_now")

    source_urls = observation.get("source_urls")
    falsification = observation.get("falsification")
    cards = observation.get("cards")
    if not isinstance(source_urls, (list, tuple)) or not source_urls:
        raise ValueError("observation requires at least one source_url")
    if not isinstance(falsification, (list, tuple)) or not falsification:
        raise ValueError("observation requires falsification criteria")
    if not isinstance(cards, (list, tuple)) or not cards:
        raise ValueError("observation requires card expressions")

    card_id = update["card_id"]
    selected_card = next(
        (dict(card) for card in cards if str(card.get("card_id", "")).strip() == card_id),
        None,
    )
    if selected_card is None:
        raise ValueError("repricing card must resolve to an observation card expression")

    observed_at, decision_lag_minutes, latency_bucket = _decision_latency(
        observation.get("observed_at"), update["as_of"]
    )
    decision = str(update["decision"])
    return {
        "schema": "opportunity-decision-packet.v1",
        "player_id": player_id,
        "player": player,
        "sport": str(observation.get("sport", "")).strip(),
        "headline": headline,
        "signal_kind": str(observation.get("signal_kind", "")).strip(),
        "catalyst_at": update["catalyst_at"],
        "observed_at": observed_at,
        "as_of": update["as_of"],
        "observation_to_decision_lag_minutes": decision_lag_minutes,
        "decision_latency_bucket": latency_bucket,
        "why_now": why_now,
        "thesis": thesis,
        "falsification": [str(item) for item in falsification],
        "source_urls": [str(item) for item in source_urls],
        "card": selected_card,
        "pricing": {
            "verified": update["market_price_verified"],
            "repricing_pct": update["market_repricing_pct"],
            "blocking_reason": update["verification_blocking_reason"],
            "evidence_ids": list(update["pricing_evidence_ids"]),
        },
        "decision": decision,
        "actionable": decision in _ACTIONABLE,
        "stage": update["stage"],
        "engine_action": update["engine_action"],
        "edge_conviction": update["edge_conviction"],
        "evidence_confidence": update["evidence_confidence"],
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
        description="Build one reviewable Opportunity Engine decision packet."
    )
    parser.add_argument("--observation", required=True, help="Sourced Radar observation JSON")
    parser.add_argument("--collection", required=True, help="Authoritative repricing collection JSON")
    parser.add_argument("-o", "--output", default="-", help="Output path, or - for stdout")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        observation = _read_json(args.observation)
        collection = _read_json(args.collection)
        if not isinstance(observation, dict) or not isinstance(collection, dict):
            raise ValueError("observation and collection JSON must be objects")
        _write_json(build_opportunity_decision_packet(observation, collection), args.output)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        sys.stderr.write(f"opportunity-decision-packet error: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
