"""Portfolio concentration controls layered on top of approved capital allocations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ExposurePolicy:
    max_player_pct: float = 0.15
    max_sport_pct: float = 0.35
    max_set_family_pct: float = 0.20
    max_single_thesis_pct: float = 0.20
    max_correlated_bucket_pct: float = 0.25

    def __post_init__(self) -> None:
        for name in (
            "max_player_pct",
            "max_sport_pct",
            "max_set_family_pct",
            "max_single_thesis_pct",
            "max_correlated_bucket_pct",
        ):
            value = getattr(self, name)
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1].")


@dataclass(frozen=True)
class PositionExposure:
    card_id: str
    market_value: float
    player_id: str
    sport: str
    set_family: str
    thesis_id: str
    correlated_bucket: str

    def __post_init__(self) -> None:
        if self.market_value < 0:
            raise ValueError("market_value cannot be negative.")


@dataclass(frozen=True)
class CandidateExposure:
    card_id: str
    player_id: str
    sport: str
    set_family: str
    thesis_id: str
    correlated_bucket: str


def _group_total(positions: list[PositionExposure], *, field: str, value: str) -> float:
    return sum(position.market_value for position in positions if getattr(position, field) == value)


def exposure_headroom(*, portfolio_value: float, positions: list[PositionExposure], candidate: CandidateExposure, policy: ExposurePolicy | None = None) -> dict[str, Any]:
    policy = policy or ExposurePolicy()
    if portfolio_value <= 0:
        raise ValueError("portfolio_value must be positive.")

    dimensions = {
        "player": ("player_id", candidate.player_id, policy.max_player_pct),
        "sport": ("sport", candidate.sport, policy.max_sport_pct),
        "set_family": ("set_family", candidate.set_family, policy.max_set_family_pct),
        "thesis": ("thesis_id", candidate.thesis_id, policy.max_single_thesis_pct),
        "correlated_bucket": ("correlated_bucket", candidate.correlated_bucket, policy.max_correlated_bucket_pct),
    }

    result: dict[str, Any] = {}
    for name, (field, value, cap_pct) in dimensions.items():
        current = _group_total(positions, field=field, value=value)
        cap_dollars = portfolio_value * cap_pct
        result[name] = {
            "current": round(current, 2),
            "cap": round(cap_dollars, 2),
            "headroom": round(max(cap_dollars - current, 0.0), 2),
            "at_or_over_cap": current >= cap_dollars,
        }
    return result


def apply_exposure_caps(allocations: list[Mapping[str, Any]], exposure_by_card: Mapping[str, CandidateExposure], *, portfolio_value: float, positions: list[PositionExposure] | None = None, policy: ExposurePolicy | None = None) -> list[dict[str, Any]]:
    """Clamp approved allocations to concentration headroom without ever increasing them."""
    policy = policy or ExposurePolicy()
    positions = list(positions or [])
    results: list[dict[str, Any]] = []

    for raw in allocations:
        row = dict(raw)
        requested = float(row.get("allocation") or 0.0)

        if not row.get("ready") or requested <= 0:
            row["exposure_adjusted_allocation"] = 0.0
            row["exposure_blockers"] = list(row.get("blockers") or [])
            results.append(row)
            continue

        card_id = str(row.get("card_id"))
        exposure = exposure_by_card.get(card_id)
        if exposure is None:
            row["exposure_adjusted_allocation"] = 0.0
            row["exposure_blockers"] = ["missing_exposure_metadata"]
            results.append(row)
            continue

        headroom = exposure_headroom(portfolio_value=portfolio_value, positions=positions, candidate=exposure, policy=policy)
        allowed = min(requested, *(dimension["headroom"] for dimension in headroom.values()))
        blockers = [f"{name}_cap_reached" for name, dimension in headroom.items() if dimension["headroom"] <= 0]
        adjusted = round(max(allowed, 0.0), 2)

        row["exposure_adjusted_allocation"] = adjusted
        row["exposure_blockers"] = blockers
        row["exposure_headroom"] = headroom
        results.append(row)

        if adjusted > 0:
            positions.append(PositionExposure(card_id=card_id, market_value=adjusted, player_id=exposure.player_id, sport=exposure.sport, set_family=exposure.set_family, thesis_id=exposure.thesis_id, correlated_bucket=exposure.correlated_bucket))

    return results
