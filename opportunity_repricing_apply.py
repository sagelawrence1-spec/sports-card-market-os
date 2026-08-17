"""Apply authoritative repricing proof back into a live Opportunity Radar observation."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_radar import evaluate_live_observation


def _aware(value: str, *, field: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def apply_repricing_collection(
    observation: Mapping[str, Any], collection: Mapping[str, Any]
) -> dict[str, Any]:
    """Return a durable decision update from one Radar observation + repricing proof.

    The collection artifact is not trusted merely because it says pricing is verified.
    Its player/card/catalyst identity must bind back to the exact observation being
    upgraded. Unverified collections remain non-actionable and preserve their blocker.
    """
    if collection.get("schema") != "opportunity-repricing-collection.v1":
        raise ValueError("unsupported repricing collection schema")

    player_id = str(observation.get("player_id", "")).strip()
    if not player_id or str(collection.get("player_id", "")).strip() != player_id:
        raise ValueError("repricing collection player_id must match observation")

    card_id = str(collection.get("card_id", "")).strip()
    card_ids = {str(card.get("card_id", "")).strip() for card in observation.get("cards", ())}
    if not card_id or card_id not in card_ids:
        raise ValueError("repricing collection card_id must be an observation card expression")

    verification = collection.get("verification")
    if not isinstance(verification, Mapping) or verification.get("schema") != "opportunity-repricing.v1":
        raise ValueError("repricing collection requires opportunity-repricing.v1 verification")

    observed_at = _aware(str(observation.get("observed_at", "")), field="observed_at")
    catalyst_at = _aware(str(verification.get("catalyst_at", "")), field="verification.catalyst_at")
    as_of = _aware(str(verification.get("as_of", "")), field="verification.as_of")
    if catalyst_at != observed_at:
        raise ValueError("repricing catalyst_at must match observation observed_at")
    if as_of < catalyst_at:
        raise ValueError("repricing as_of cannot precede catalyst_at")

    verified = bool(verification.get("verified", False))
    repricing_pct = verification.get("repricing_pct")
    payload = dict(observation)
    if verified:
        if repricing_pct is None:
            raise ValueError("verified repricing collection requires repricing_pct")
        payload["market_price_verified"] = True
        payload["market_repricing_pct"] = float(repricing_pct)
    else:
        payload["market_price_verified"] = False
        payload.pop("market_repricing_pct", None)

    candidate = evaluate_live_observation(payload)
    evidence_ids = verification.get("evidence_ids", ())
    if not isinstance(evidence_ids, (list, tuple)):
        raise ValueError("verification evidence_ids must be a list or tuple")

    blocker = None if verified else str(verification.get("blocking_reason") or "authoritative_market_repricing_unverified")
    return {
        "schema": "opportunity-radar-repricing-update.v1",
        "player_id": player_id,
        "card_id": card_id,
        "catalyst_at": catalyst_at.isoformat(),
        "as_of": as_of.isoformat(),
        "market_price_verified": verified,
        "market_repricing_pct": float(repricing_pct) if verified else None,
        "verification_blocking_reason": blocker,
        "pricing_evidence_ids": list(evidence_ids),
        "decision": candidate.decision,
        "stage": candidate.thesis.stage.value,
        "engine_action": candidate.thesis.action.value,
        "edge_conviction": candidate.thesis.edge_conviction,
        "evidence_confidence": candidate.thesis.evidence_confidence,
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
        description="Apply authoritative Product Research repricing proof to one Opportunity Radar observation."
    )
    parser.add_argument("--observation", required=True, help="Sourced Radar observation JSON path")
    parser.add_argument("--collection", required=True, help="opportunity-repricing-collection.v1 JSON path")
    parser.add_argument("-o", "--output", default="-", help="Output opportunity-radar-repricing-update.v1 path, or -")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        observation = _read_json(args.observation)
        collection = _read_json(args.collection)
        if not isinstance(observation, dict) or not isinstance(collection, dict):
            raise ValueError("observation and collection JSON must be objects")
        _write_json(apply_repricing_collection(observation, collection), args.output)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        sys.stderr.write(f"opportunity-repricing-apply error: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
