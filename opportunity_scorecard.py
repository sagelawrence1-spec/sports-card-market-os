"""Aggregate immutable Opportunity Engine outcomes into a proof-oriented scorecard."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import isfinite
from statistics import median
from typing import Any, Iterable, Mapping

OUTCOME_SCHEMA = "opportunity-outcome.v1"
SCORECARD_SCHEMA = "opportunity-scorecard.v1"
_ACTIONABLE = {"START_POSITION", "ADD"}
_LATENCY_BUCKETS = {"UNDER_6H", "6_TO_24H", "OVER_24H", "UNKNOWN"}


@dataclass(frozen=True)
class OpportunityScorecardPolicy:
    min_settled_outcomes: int = 5
    min_distinct_players: int = 3
    min_hit_rate: float = 0.50
    min_median_net_return: float = 0.0

    def validate(self) -> None:
        if int(self.min_settled_outcomes) < 1:
            raise ValueError("min_settled_outcomes must be at least 1")
        if int(self.min_distinct_players) < 1:
            raise ValueError("min_distinct_players must be at least 1")
        if not 0.0 <= float(self.min_hit_rate) <= 1.0:
            raise ValueError("min_hit_rate must be between 0 and 1")
        if not isfinite(float(self.min_median_net_return)):
            raise ValueError("min_median_net_return must be finite")


def _identity(outcome: Mapping[str, Any]) -> tuple[str, str, str, str]:
    player_id = str(outcome.get("player_id", "")).strip()
    card_id = str(outcome.get("card_id", "")).strip()
    catalyst_at = str(outcome.get("catalyst_at", "")).strip()
    decision_as_of = str(outcome.get("decision_as_of", "")).strip()
    if not all((player_id, card_id, catalyst_at, decision_as_of)):
        raise ValueError("opportunity outcome identity is incomplete")
    return player_id, card_id, catalyst_at, decision_as_of


def build_opportunity_scorecard(
    outcomes: Iterable[Mapping[str, Any]],
    *,
    policy: OpportunityScorecardPolicy | None = None,
) -> dict[str, Any]:
    """Build a deterministic, no-hindsight aggregate scorecard from settled outcomes.

    This function never reconstructs prices or mutates decisions. It consumes only
    already-settled ``opportunity-outcome.v1`` records and fails closed on duplicate
    decision identities so a repeated winner cannot inflate the track record.
    """
    policy = policy or OpportunityScorecardPolicy()
    policy.validate()

    rows = list(outcomes)
    if not rows:
        raise ValueError("at least one settled opportunity outcome is required")

    seen: set[tuple[str, str, str, str]] = set()
    net_returns: list[float] = []
    hits = 0
    players: set[str] = set()
    grades: Counter[str] = Counter()
    by_decision: dict[str, list[float]] = defaultdict(list)
    by_player: dict[str, list[float]] = defaultdict(list)
    by_latency: dict[str, list[float]] = defaultdict(list)

    for outcome in rows:
        if outcome.get("schema") != OUTCOME_SCHEMA:
            raise ValueError("unsupported opportunity outcome schema")
        identity = _identity(outcome)
        if identity in seen:
            raise ValueError("duplicate settled opportunity outcome identity")
        seen.add(identity)

        decision = str(outcome.get("decision", "")).strip()
        if decision not in _ACTIONABLE:
            raise ValueError("scorecard only accepts settled actionable opportunity outcomes")

        net_return = float(outcome.get("net_return"))
        if not isfinite(net_return):
            raise ValueError("opportunity outcome net_return must be finite")
        hit = outcome.get("hit")
        if not isinstance(hit, bool):
            raise ValueError("opportunity outcome hit must be boolean")
        if hit != (net_return >= 0.0):
            raise ValueError("opportunity outcome hit is inconsistent with net_return")

        grade = str(outcome.get("grade", "")).strip().upper()
        if grade not in {"A", "B", "C", "D", "F"}:
            raise ValueError("opportunity outcome grade is invalid")

        latency_bucket = str(outcome.get("decision_latency_bucket") or "UNKNOWN").strip().upper()
        if latency_bucket not in _LATENCY_BUCKETS:
            raise ValueError("opportunity outcome decision latency bucket is invalid")

        player_id = identity[0]
        players.add(player_id)
        net_returns.append(net_return)
        hits += int(hit)
        grades[grade] += 1
        by_decision[decision].append(net_return)
        by_player[player_id].append(net_return)
        by_latency[latency_bucket].append(net_return)

    settled = len(rows)
    hit_rate = hits / settled
    median_return = median(net_returns)
    mean_return = sum(net_returns) / settled

    blockers: list[str] = []
    if settled < int(policy.min_settled_outcomes):
        blockers.append("insufficient_settled_outcomes")
    if len(players) < int(policy.min_distinct_players):
        blockers.append("insufficient_distinct_players")
    if hit_rate < float(policy.min_hit_rate):
        blockers.append("hit_rate_below_threshold")
    if median_return < float(policy.min_median_net_return):
        blockers.append("median_net_return_below_threshold")

    def summarize(values: list[float]) -> dict[str, Any]:
        bucket_hits = sum(value >= 0.0 for value in values)
        return {
            "count": len(values),
            "hits": bucket_hits,
            "hit_rate": bucket_hits / len(values),
            "mean_net_return": sum(values) / len(values),
            "median_net_return": median(values),
        }

    return {
        "schema": SCORECARD_SCHEMA,
        "status": "EVIDENCE_THRESHOLD_MET" if not blockers else "INSUFFICIENT_EVIDENCE",
        "proof_blockers": blockers,
        "settled_outcomes": settled,
        "distinct_players": len(players),
        "hits": hits,
        "misses": settled - hits,
        "hit_rate": hit_rate,
        "mean_net_return": mean_return,
        "median_net_return": median_return,
        "grade_distribution": {grade: grades.get(grade, 0) for grade in ("A", "B", "C", "D", "F")},
        "by_decision": {key: summarize(by_decision[key]) for key in sorted(by_decision)},
        "by_player": {key: summarize(by_player[key]) for key in sorted(by_player)},
        "by_decision_latency": {key: summarize(by_latency[key]) for key in sorted(by_latency)},
        "policy": {
            "min_settled_outcomes": int(policy.min_settled_outcomes),
            "min_distinct_players": int(policy.min_distinct_players),
            "min_hit_rate": float(policy.min_hit_rate),
            "min_median_net_return": float(policy.min_median_net_return),
        },
    }
