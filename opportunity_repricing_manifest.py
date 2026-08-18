"""Human-executable collection manifest for authoritative Opportunity Radar repricing proof."""
from __future__ import annotations

import re
from typing import Any, Mapping

_PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}


def _safe_filename(value: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-.").lower()
    return token or "unknown"


def build_collection_manifest(
    plan: Mapping[str, Any],
    *,
    max_requests: int = 10,
    include_p2: bool = False,
) -> dict[str, Any]:
    """Convert a repricing plan into a short, ordered Product Research work queue.

    This artifact is deliberately operational only. It does not alter Radar ranking,
    repricing verification, or capital decisions. The collector is instructed to export
    the full search result set so manual cherry-picking cannot contaminate proof.
    """
    if plan.get("schema") != "opportunity-repricing-plan.v1":
        raise ValueError("unsupported repricing plan schema")
    if not isinstance(max_requests, int) or isinstance(max_requests, bool) or max_requests <= 0:
        raise ValueError("max_requests must be a positive integer")

    raw_requests = plan.get("requests")
    if not isinstance(raw_requests, list):
        raise ValueError("repricing plan requests must be a list")

    eligible: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in raw_requests:
        if not isinstance(row, Mapping):
            raise ValueError("repricing request must be an object")
        priority = str(row.get("collection_priority", ""))
        if priority not in _PRIORITY_ORDER:
            raise ValueError("repricing request requires P0/P1/P2 collection_priority")
        if priority == "P2" and not include_p2:
            continue

        player_id = str(row.get("player_id", "")).strip()
        card_id = str(row.get("card_id", "")).strip()
        if not player_id or not card_id:
            raise ValueError("repricing request requires player_id and card_id")
        identity = (player_id, card_id)
        if identity in seen:
            raise ValueError("duplicate player/card repricing request")
        seen.add(identity)

        if row.get("source_type") != "EBAY_PRODUCT_RESEARCH":
            raise ValueError("collection manifest only supports authoritative eBay Product Research")
        pre_start = str(row.get("pre_start", "")).strip()
        queryable_post_end = str(row.get("queryable_post_end", "")).strip()
        catalyst_at = str(row.get("catalyst_at", "")).strip()
        if not pre_start or not queryable_post_end or not catalyst_at:
            raise ValueError("repricing request requires catalyst and collection windows")

        eligible.append(dict(row))

    eligible.sort(
        key=lambda row: (
            _PRIORITY_ORDER[str(row["collection_priority"])],
            row.get("candidate_rank") if row.get("candidate_rank") is not None else 999,
            row.get("card_priority") or 999,
            str(row["player_id"]),
            str(row["card_id"]),
        )
    )
    selected = eligible[:max_requests]

    items: list[dict[str, Any]] = []
    for position, row in enumerate(selected, start=1):
        player = str(row.get("player") or row["player_id"])
        card_label = str(row.get("card_label") or row["card_id"])
        filename = f"{position:02d}-{_safe_filename(player)}-{_safe_filename(card_label)}.csv"
        items.append(
            {
                "queue_position": position,
                "collection_priority": row["collection_priority"],
                "collection_priority_reason": row.get("collection_priority_reason"),
                "player_id": row["player_id"],
                "player": row.get("player"),
                "card_id": row["card_id"],
                "card_label": row.get("card_label"),
                "stage": row.get("stage"),
                "decision": row.get("decision"),
                "catalyst_at": row["catalyst_at"],
                "sold_window_start": row["pre_start"],
                "sold_window_end": row["queryable_post_end"],
                "window_status": row.get("status"),
                "expected_export_filename": filename,
                "collection_instruction": (
                    "In eBay Product Research, search the exact canonical card identity, set the sold-date "
                    "window shown here, and export the complete result set without hand-filtering rows. "
                    "Preserve item ID, title, sold date, sold price, shipping, currency, and item URL."
                ),
            }
        )

    return {
        "schema": "opportunity-repricing-collection-manifest.v1",
        "source_scan_generated_at": plan.get("source_scan_generated_at"),
        "plan_as_of": plan.get("as_of"),
        "include_p2": include_p2,
        "max_requests": max_requests,
        "eligible_request_count": len(eligible),
        "selected_request_count": len(items),
        "remaining_request_count": max(0, len(eligible) - len(items)),
        "priority_counts": {
            priority: sum(item["collection_priority"] == priority for item in items)
            for priority in ("P0", "P1", "P2")
        },
        "items": items,
    }
