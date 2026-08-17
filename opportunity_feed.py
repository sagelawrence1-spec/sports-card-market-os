"""Validated external feed contract for Opportunity Radar observations.

This module is the narrow boundary between sourced observation feeds and the
product-facing Radar engine. It validates batch provenance and chronology, then
produces the same durable scan artifact used elsewhere in the Opportunity Engine.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from opportunity_radar import scan_live_observations
from opportunity_report import build_radar_scan_artifact

FEED_SCHEMA = "opportunity-radar-feed.v1"


def _aware_utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def process_opportunity_feed(feed: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one external Radar feed and return a durable scan artifact.

    The feed timestamp is the hard point-in-time boundary: observations from the
    future are rejected rather than allowed to leak into an earlier Radar scan.
    Individual malformed observations remain visible as Radar batch failures.
    """
    if feed.get("schema") != FEED_SCHEMA:
        raise ValueError(f"unsupported Opportunity Radar feed schema: {feed.get('schema')}")

    generated_at = _aware_utc(feed.get("generated_at"), field="generated_at")
    publisher = str(feed.get("publisher", "")).strip()
    if not publisher:
        raise ValueError("publisher is required")

    observations = feed.get("observations")
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
        raise ValueError("observations must be a sequence")

    normalized: list[Mapping[str, Any]] = []
    for index, observation in enumerate(observations):
        if not isinstance(observation, Mapping):
            raise ValueError(f"observation {index} must be an object")
        observed_at = _aware_utc(observation.get("observed_at"), field=f"observation {index} observed_at")
        if observed_at > generated_at:
            raise ValueError(f"observation {index} occurs after feed generated_at")
        normalized.append(observation)

    report = scan_live_observations(normalized)
    artifact = build_radar_scan_artifact(report, generated_at=generated_at.isoformat())
    artifact["feed"] = {
        "schema": FEED_SCHEMA,
        "publisher": publisher,
        "generated_at": generated_at.isoformat(),
        "observation_count": len(normalized),
    }
    return artifact
