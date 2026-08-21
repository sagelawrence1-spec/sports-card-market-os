from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from entity_resolution_gate import RegistryExpansionPolicy, assess_registry_expansion

_CANONICAL_FIELDS = (
    "player",
    "year",
    "manufacturer",
    "set_name",
    "card_number",
    "parallel",
    "autograph",
)


def _norm_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _canonical_identity(record: Mapping[str, Any]) -> tuple[Any, ...] | None:
    values: list[Any] = []
    for field in _CANONICAL_FIELDS:
        value = record.get(field)
        if field == "year":
            try:
                year = int(value)
            except (TypeError, ValueError):
                return None
            if year < 1800 or year > 2200:
                return None
            values.append(year)
        elif field == "autograph":
            if value in (True, 1, "1"):
                values.append(1)
            elif value in (False, 0, "0"):
                values.append(0)
            else:
                return None
        else:
            normalized = _norm_text(value)
            if not normalized:
                return None
            values.append(normalized)
    return tuple(values)


def gate_registry_batch(
    evaluation: Mapping[str, Any],
    additions: Iterable[Mapping[str, Any]],
    *,
    existing_card_ids: Iterable[str] = (),
    existing_records: Iterable[Mapping[str, Any]] = (),
    policy: RegistryExpansionPolicy | None = None,
) -> dict[str, Any]:
    """Gate a proposed canonical-registry batch atomically.

    A batch is approved only when every proposed record has a stable ``card_id``,
    explicit ``family``, and complete canonical card identity. Both card IDs and the
    normalized canonical identity must be unique against the existing registry and
    within the proposed batch. Every affected family must also pass the leakage-safe
    expansion gate. No partial approval is returned.
    """

    records = [dict(record) for record in additions]
    existing = {str(card_id).strip() for card_id in existing_card_ids if str(card_id).strip()}
    existing_identities = {
        identity
        for record in existing_records
        if (identity := _canonical_identity(record)) is not None
    }
    seen: set[str] = set()
    seen_identities: set[tuple[Any, ...]] = set()
    record_blockers: list[dict[str, Any]] = []
    families: set[str] = set()

    for index, record in enumerate(records):
        card_id = str(record.get("card_id") or "").strip()
        family = str(record.get("family") or "").strip()
        blockers: list[str] = []

        if not card_id:
            blockers.append("missing_card_id")
        elif card_id in existing:
            blockers.append("card_id_already_exists")
        elif card_id in seen:
            blockers.append("duplicate_card_id_in_batch")
        else:
            seen.add(card_id)

        if not family:
            blockers.append("missing_family")
        else:
            families.add(family)

        identity = _canonical_identity(record)
        if identity is None:
            blockers.append("missing_or_invalid_canonical_identity")
        elif identity in existing_identities:
            blockers.append("canonical_identity_already_exists")
        elif identity in seen_identities:
            blockers.append("duplicate_canonical_identity_in_batch")
        else:
            seen_identities.add(identity)

        if blockers:
            record_blockers.append(
                {
                    "index": index,
                    "card_id": card_id or None,
                    "family": family or None,
                    "blockers": blockers,
                }
            )

    family_gates = {
        family: assess_registry_expansion(evaluation, family, policy=policy)
        for family in sorted(families)
    }
    blocked_families = [
        family for family, gate in family_gates.items() if not gate["ready"]
    ]
    ready = bool(records) and not record_blockers and not blocked_families

    return {
        "schema": "registry-batch-gate.v2",
        "ready": ready,
        "atomic": True,
        "proposed_records": len(records),
        "affected_families": sorted(families),
        "blocked_families": blocked_families,
        "record_blockers": record_blockers,
        "family_gates": family_gates,
        "approved_card_ids": [str(record["card_id"]).strip() for record in records] if ready else [],
    }
