from __future__ import annotations

import hashlib
import json
from datetime import datetime
from math import isfinite
from typing import Iterable


_ALLOWED_DECISIONS = {"no_change", "propose_change", "defer"}


def _digest(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_reviewed_at(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("reviewed_at must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        raise ValueError("reviewed_at must include a timezone")
    return parsed.isoformat()


def _required_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _normalize_proposals(proposals: Iterable[dict] | None) -> list[dict]:
    normalized: list[dict] = []
    seen: set[str] = set()
    for index, proposal in enumerate(proposals or []):
        if not isinstance(proposal, dict):
            raise ValueError(f"proposal {index} must be an object")
        threshold_raw = proposal.get("threshold")
        if not isinstance(threshold_raw, str) or not threshold_raw.strip():
            raise ValueError(f"proposal {index} requires threshold")
        threshold = threshold_raw.strip()
        if threshold in seen:
            raise ValueError(f"duplicate threshold proposal:{threshold}")
        seen.add(threshold)
        try:
            current = float(proposal["current"])
            proposed = float(proposal["proposed"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"proposal {index} requires numeric current/proposed values") from exc
        if not isfinite(current) or not isfinite(proposed):
            raise ValueError(f"proposal {index} values must be finite")
        if current == proposed:
            raise ValueError(f"proposal {index} does not change threshold")
        normalized.append(
            {
                "threshold": threshold,
                "current": current,
                "proposed": proposed,
            }
        )
    return normalized


def build_calibration_decision_record(
    history_assessment: dict,
    *,
    decision: str,
    reviewer: str,
    reviewed_at: str,
    rationale: str,
    proposals: Iterable[dict] | None = None,
) -> dict:
    """Create an immutable, non-executing record of a human calibration decision.

    This contract deliberately cannot apply threshold changes. It records who reviewed
    a leakage-safe calibration-history gate, exactly what evidence was reviewed, and
    any proposed threshold changes for a later explicit implementation/PR.
    """

    if not isinstance(history_assessment, dict):
        raise ValueError("history_assessment must be an object")
    if history_assessment.get("schema") != "calibration-history.v1":
        raise ValueError("unsupported calibration history schema")

    decision = str(decision or "").strip()
    if decision not in _ALLOWED_DECISIONS:
        raise ValueError(f"unsupported calibration decision:{decision}")

    reviewer = _required_text(reviewer, field="reviewer")
    rationale = _required_text(rationale, field="rationale")

    normalized_proposals = _normalize_proposals(proposals)
    review_allowed = history_assessment.get("calibration_review_allowed") is True

    if decision == "propose_change":
        if not review_allowed:
            raise ValueError("cannot propose threshold changes when calibration review is blocked")
        if not normalized_proposals:
            raise ValueError("propose_change requires at least one threshold proposal")
    elif normalized_proposals:
        raise ValueError(f"{decision} cannot include threshold proposals")

    evidence_digest = _digest(history_assessment)
    reviewed_at_iso = _parse_reviewed_at(reviewed_at)

    record_core = {
        "schema": "calibration-decision.v1",
        "decision": decision,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at_iso,
        "rationale": rationale,
        "history_evidence_sha256": evidence_digest,
        "history_latest_evaluation_date": history_assessment.get("latest_evaluation_date"),
        "history_latest_mature_observations": history_assessment.get("latest_mature_observations"),
        "history_review_allowed": review_allowed,
        "proposals": normalized_proposals,
        "automatic_threshold_changes_allowed": False,
        "threshold_changes_applied": False,
    }
    return {
        **record_core,
        "record_id": f"calibration-decision:{_digest(record_core)[:24]}",
    }
