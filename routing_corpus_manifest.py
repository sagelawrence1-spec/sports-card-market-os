"""Deterministic, diversity-constrained manifest selection for routing validation."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class CorpusManifestPolicy:
    target_size: int = 25
    max_per_player: int = 2
    max_sport_share: float = 0.40
    min_distinct_sports: int = 2

    def __post_init__(self) -> None:
        if self.target_size < 1:
            raise ValueError("target_size must be positive")
        if self.max_per_player < 1:
            raise ValueError("max_per_player must be positive")
        if not 0 < self.max_sport_share <= 1:
            raise ValueError("max_sport_share must be in (0, 1]")
        if self.min_distinct_sports < 1:
            raise ValueError("min_distinct_sports must be positive")


def _stable_key(card: Mapping[str, Any], seed: str) -> str:
    card_id = str(card.get("card_id") or "")
    return hashlib.sha256(f"{seed}:{card_id}".encode("utf-8")).hexdigest()


def build_routing_corpus_manifest(
    candidates: Sequence[Mapping[str, Any]],
    *,
    policy: CorpusManifestPolicy | None = None,
    seed: str = "routing-corpus-v1",
) -> dict[str, Any]:
    """Select a reproducible validation corpus from an already eligible candidate pool.

    The caller is responsible for supplying cards that have passed the desired
    liquidity/availability screen. This function deliberately does not infer or
    fabricate liquidity. It prevents cherry-picking by using stable hashed order and
    constrains player and sport concentration.
    """
    policy = policy or CorpusManifestPolicy()
    normalized: list[Mapping[str, Any]] = []
    seen: set[str] = set()

    for card in candidates:
        card_id = str(card.get("card_id") or "").strip()
        player = str(card.get("player") or "").strip()
        sport = str(card.get("sport") or "").strip()
        if not card_id or not player or not sport:
            continue
        if card_id in seen:
            continue
        seen.add(card_id)
        normalized.append(card)

    if len(normalized) < policy.target_size:
        raise RuntimeError(
            f"eligible pool too small: {len(normalized)} < target {policy.target_size}"
        )

    available_sports = {str(card["sport"]) for card in normalized}
    if len(available_sports) < policy.min_distinct_sports:
        raise RuntimeError("eligible pool lacks required sport diversity")

    sport_cap = max(1, int(policy.target_size * policy.max_sport_share))
    selected: list[Mapping[str, Any]] = []
    player_counts: dict[str, int] = {}
    sport_counts: dict[str, int] = {}

    for card in sorted(normalized, key=lambda row: _stable_key(row, seed)):
        player = str(card["player"])
        sport = str(card["sport"])
        if player_counts.get(player, 0) >= policy.max_per_player:
            continue
        if sport_counts.get(sport, 0) >= sport_cap:
            continue

        selected.append(card)
        player_counts[player] = player_counts.get(player, 0) + 1
        sport_counts[sport] = sport_counts.get(sport, 0) + 1
        if len(selected) == policy.target_size:
            break

    if len(selected) < policy.target_size:
        raise RuntimeError(
            "eligible pool cannot satisfy corpus concentration constraints"
        )

    selected_sports = {str(card["sport"]) for card in selected}
    if len(selected_sports) < policy.min_distinct_sports:
        raise RuntimeError("selected corpus lacks required sport diversity")

    manifest = [
        {
            "card_id": str(card["card_id"]),
            "player": str(card["player"]),
            "sport": str(card["sport"]),
        }
        for card in selected
    ]
    return {
        "manifest_version": "routing-corpus.v1",
        "seed": seed,
        "target_size": policy.target_size,
        "cards": manifest,
        "distinct_cards": len(manifest),
        "distinct_players": len(player_counts),
        "distinct_sports": len(selected_sports),
        "largest_player_count": max(player_counts.values()),
        "largest_sport_count": max(sport_counts.values()),
        "largest_sport_share": max(sport_counts.values()) / len(manifest),
    }
