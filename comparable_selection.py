from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


SCHEMA = "comparable-selection.v1"
_REQUIRED_IDENTITY = ("card_id", "player", "sport", "manufacturer", "product_family", "year")


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class ComparablePolicy:
    max_results: int = 5
    max_year_distance: int = 3
    min_score: int = 60

    def validate(self) -> None:
        if self.max_results < 1:
            raise ValueError("max_results must be >= 1")
        if self.max_year_distance < 0:
            raise ValueError("max_year_distance must be >= 0")
        if not 0 <= self.min_score <= 100:
            raise ValueError("min_score must be between 0 and 100")


def _identity_errors(card: dict[str, Any]) -> list[str]:
    errors = []
    for field in _REQUIRED_IDENTITY:
        if card.get(field) in (None, ""):
            errors.append(f"missing_{field}")
    if _int(card.get("year")) is None:
        errors.append("invalid_year")
    return errors


def _hard_rejection(target: dict[str, Any], candidate: dict[str, Any], policy: ComparablePolicy) -> str | None:
    if _identity_errors(candidate):
        return "incomplete_identity"
    if _norm(candidate["card_id"]) == _norm(target["card_id"]):
        return "same_card"
    for field in ("player", "sport", "manufacturer", "product_family"):
        if _norm(candidate[field]) != _norm(target[field]):
            return f"{field}_mismatch"

    target_grader = _norm(target.get("grader"))
    candidate_grader = _norm(candidate.get("grader"))
    if target_grader != candidate_grader:
        return "grader_mismatch"
    if target_grader and _int(target.get("grade")) != _int(candidate.get("grade")):
        return "grade_mismatch"

    year_distance = abs(_int(candidate["year"]) - _int(target["year"]))
    if year_distance > policy.max_year_distance:
        return "year_distance"
    return None


def _score(target: dict[str, Any], candidate: dict[str, Any], policy: ComparablePolicy) -> tuple[int, dict[str, int]]:
    target_year = _int(target["year"])
    candidate_year = _int(candidate["year"])
    year_distance = abs(candidate_year - target_year)
    year_score = round(35 * (1 - year_distance / max(policy.max_year_distance + 1, 1)))

    rookie_score = 15 if bool(candidate.get("rookie_flag")) == bool(target.get("rookie_flag")) else 0
    auto_score = 15 if bool(candidate.get("autograph")) == bool(target.get("autograph")) else 0

    target_serial = _int(target.get("serial_number"))
    candidate_serial = _int(candidate.get("serial_number"))
    if target_serial is None and candidate_serial is None:
        scarcity_score = 20
    elif target_serial and candidate_serial:
        ratio = max(target_serial, candidate_serial) / min(target_serial, candidate_serial)
        scarcity_score = 20 if ratio <= 1.5 else 12 if ratio <= 3 else 4
    else:
        scarcity_score = 0

    parallel_score = 15 if _norm(candidate.get("parallel_family")) == _norm(target.get("parallel_family")) else 0
    components = {
        "year": year_score,
        "rookie": rookie_score,
        "autograph": auto_score,
        "scarcity": scarcity_score,
        "parallel": parallel_score,
    }
    return min(100, sum(components.values())), components


def select_hierarchy_comparables(
    target: dict[str, Any],
    candidates: Iterable[dict[str, Any]],
    *,
    policy: ComparablePolicy | None = None,
) -> dict[str, Any]:
    """Select deterministic same-player hierarchy comparables.

    This deliberately starts narrow: same player, sport, manufacturer, product family,
    and grade identity are hard boundaries. Broader peer-player substitution belongs
    behind a separately measured policy rather than being silently mixed into value.
    """
    policy = policy or ComparablePolicy()
    policy.validate()
    target_errors = _identity_errors(target)
    if target_errors:
        raise ValueError(f"target has invalid identity: {','.join(target_errors)}")

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    seen: set[str] = set()

    for candidate in candidates:
        card_id = _norm(candidate.get("card_id"))
        if not card_id:
            rejected.append({"card_id": "", "reason": "incomplete_identity"})
            continue
        if card_id in seen:
            rejected.append({"card_id": candidate.get("card_id", ""), "reason": "duplicate_candidate"})
            continue
        seen.add(card_id)

        reason = _hard_rejection(target, candidate, policy)
        if reason:
            rejected.append({"card_id": candidate.get("card_id", ""), "reason": reason})
            continue
        score, components = _score(target, candidate, policy)
        if score < policy.min_score:
            rejected.append({"card_id": candidate["card_id"], "reason": "below_min_score"})
            continue
        accepted.append({"card_id": candidate["card_id"], "score": score, "components": components})

    accepted.sort(key=lambda row: (-row["score"], _norm(row["card_id"])))
    selected = accepted[: policy.max_results]
    overflow = accepted[policy.max_results :]
    rejected.extend({"card_id": row["card_id"], "reason": "ranked_out"} for row in overflow)

    return {
        "schema": SCHEMA,
        "target_card_id": target["card_id"],
        "policy": {
            "max_results": policy.max_results,
            "max_year_distance": policy.max_year_distance,
            "min_score": policy.min_score,
        },
        "selected": selected,
        "rejected": rejected,
        "eligible_count": len(accepted),
        "selected_count": len(selected),
    }
