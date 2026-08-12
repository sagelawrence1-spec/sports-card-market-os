from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from entity_matcher import MatchDecision, SportsCardEntityMatcher, norm


@dataclass
class AliasRecord:
    title_key: str
    approvals_by_asset: Dict[str, Set[str]] = field(default_factory=dict)
    rejected_asset_ids: Set[str] = field(default_factory=set)

    @property
    def conflicting(self) -> bool:
        approved = [asset_id for asset_id, reviewers in self.approvals_by_asset.items() if reviewers]
        return len(approved) > 1


class AdjudicatedAliasRegistry:
    """Precision-first marketplace-title alias registry.

    Aliases are candidate-routing hints only. They never bypass the canonical
    SportsCardEntityMatcher. An alias activates only after independent verified
    approvals reach ``min_approvals`` and any conflicting approved assignment
    fails closed.
    """

    def __init__(self, min_approvals: int = 2):
        if min_approvals < 2:
            raise ValueError("min_approvals must be at least 2")
        self.min_approvals = min_approvals
        self._records: Dict[str, AliasRecord] = {}

    @staticmethod
    def _key(title: str) -> str:
        return norm(title)

    def record_approval(self, title: str, asset_id: str, reviewer_id: str) -> None:
        key = self._key(title)
        if not key or not asset_id or not reviewer_id:
            raise ValueError("title, asset_id, and reviewer_id are required")
        record = self._records.setdefault(key, AliasRecord(title_key=key))
        record.approvals_by_asset.setdefault(asset_id, set()).add(reviewer_id)
        record.rejected_asset_ids.discard(asset_id)

    def record_rejection(self, title: str, asset_id: str) -> None:
        key = self._key(title)
        if not key or not asset_id:
            raise ValueError("title and asset_id are required")
        record = self._records.setdefault(key, AliasRecord(title_key=key))
        record.rejected_asset_ids.add(asset_id)
        record.approvals_by_asset.pop(asset_id, None)

    def resolved_asset_id(self, title: str) -> Optional[str]:
        record = self._records.get(self._key(title))
        if record is None or record.conflicting:
            return None
        qualified = [
            asset_id
            for asset_id, reviewers in record.approvals_by_asset.items()
            if len(reviewers) >= self.min_approvals and asset_id not in record.rejected_asset_ids
        ]
        return qualified[0] if len(qualified) == 1 else None

    def diagnostics(self, title: str) -> dict:
        record = self._records.get(self._key(title))
        if record is None:
            return {"known": False, "active": False, "conflicting": False}
        counts = {asset_id: len(reviewers) for asset_id, reviewers in record.approvals_by_asset.items()}
        resolved = self.resolved_asset_id(title)
        return {
            "known": True,
            "active": resolved is not None,
            "resolved_asset_id": resolved,
            "conflicting": record.conflicting,
            "approval_counts": counts,
            "rejected_asset_ids": sorted(record.rejected_asset_ids),
        }


class PersistentAliasRegistry:
    """Read adjudicated aliases persisted by EvidenceStore.

    The store remains the source of truth for human review decisions. This
    adapter exposes the same lookup surface used by AliasAwareEntityRouter so
    restart-safe review history can improve routing without weakening canonical
    identity checks.
    """

    def __init__(self, store, min_approvals: int = 2):
        if min_approvals < 2:
            raise ValueError("min_approvals must be at least 2")
        self.store = store
        self.min_approvals = min_approvals

    def resolved_asset_id(self, title: str) -> Optional[str]:
        return self.store.resolved_alias_asset_id(title, min_approvals=self.min_approvals)

    def diagnostics(self, title: str) -> dict:
        return self.store.alias_diagnostics(title, min_approvals=self.min_approvals)


class AliasAwareEntityRouter:
    """Use verified aliases to select a candidate, then re-run canonical checks."""

    def __init__(
        self,
        assets_by_id: Dict[str, dict],
        registry,
        matcher: Optional[SportsCardEntityMatcher] = None,
    ):
        self.assets_by_id = assets_by_id
        self.registry = registry
        self.matcher = matcher or SportsCardEntityMatcher()

    def match(self, title: str) -> Optional[MatchDecision]:
        asset_id = self.registry.resolved_asset_id(title)
        if asset_id is None:
            return None
        asset = self.assets_by_id.get(asset_id)
        if asset is None:
            return MatchDecision(False, 0.0, "alias_target_missing", {"alias_asset_id": asset_id})

        decision = self.matcher.match(asset, title)
        decision.diagnostics["alias_candidate"] = asset_id
        decision.diagnostics["alias_verified"] = True
        return decision
