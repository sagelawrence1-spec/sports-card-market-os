from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from entity_resolution_gate import RegistryExpansionPolicy, assess_registry_expansion


def gate_registry_batch(
    evaluation: Mapping[str, Any],
    additions: Iterable[Mapping[str, Any]],
    *,
    existing_card_ids: Iterable[str] = (),
    policy: RegistryExpansionPolicy | None = None,
) -> dict[str, Any]:
    """Gate a proposed canonical-registry batch atomically.

    A batch is approved only when every proposed record has a stable ``card_id`` and
    explicit ``family``, introduces no duplicate identity, and every affected family
    passes the leakage-safe expansion gate. No partial approval is returned: if one
    family or record is unsafe, the entire batch remains blocked.
    """

    records = [dict(record) for record in additions]
    existing = {str(card_id).strip() for card_id in existing_card_ids if str(card_id).strip()}
    seen: set[str] = set()
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
        "schema": "registry-batch-gate.v1",
        "ready": ready,
        "atomic": True,
        "proposed_records": len(records),
        "affected_families": sorted(families),
        "blocked_families": blocked_families,
        "record_blockers": record_blockers,
        "family_gates": family_gates,
        "approved_card_ids": [str(record["card_id"]).strip() for record in records] if ready else [],
    }
