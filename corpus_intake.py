from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Iterable, Mapping


SENSITIVE_KEYS = {
    "buyer",
    "buyer_name",
    "buyer_username",
    "seller",
    "seller_name",
    "seller_username",
    "email",
    "phone",
    "address",
    "shipping_address",
}

ID_KEYS = ("item_id", "ebay_item_id", "source_item_id")
TITLE_KEYS = ("title", "item_title", "listing_title")
PRICE_KEYS = ("sold_price", "price", "sale_price")
DATE_KEYS = ("sold_date", "date_sold", "sale_date", "end_date")
CURRENCY_KEYS = ("currency", "currency_code")

_PRICE_RANGE_RE = re.compile(r"\d[\d,.]*\s*[-–—]\s*\d[\d,.]*")


@dataclass(frozen=True)
class CorpusIntakePolicy:
    require_usd: bool = True
    require_item_id: bool = False
    max_missing_required_share: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.max_missing_required_share <= 1.0:
            raise ValueError("max_missing_required_share must be between 0 and 1")


def _first(row: Mapping[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _normalized_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _parse_price(value: Any) -> float | None:
    if value is None:
        return None
    text = _normalized_text(value)
    if not text or _PRICE_RANGE_RE.search(text):
        return None
    cleaned = re.sub(r"[^0-9.]", "", text.replace(",", ""))
    if cleaned.count(".") > 1 or not cleaned:
        return None
    try:
        price = float(cleaned)
    except ValueError:
        return None
    return price if price > 0 else None


def _stable_item_id(row: Mapping[str, Any]) -> str | None:
    value = _first(row, ID_KEYS)
    if value in (None, ""):
        return None
    text = _normalized_text(value)
    match = re.search(r"(\d{8,})", text)
    return match.group(1) if match else text


def _fingerprint(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sanitize_product_research_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    policy: CorpusIntakePolicy | None = None,
) -> dict[str, Any]:
    """Normalize a genuine Product Research export into a reproducible corpus fixture.

    The sanitizer deliberately preserves only evidence needed for parser/matcher auditing.
    Seller/buyer contact fields are removed. Ambiguous prices, missing core fields, and
    non-USD rows (by default) fail closed into the rejected collection rather than being
    silently coerced into usable evidence.
    """
    policy = policy or CorpusIntakePolicy()
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicates = 0

    input_rows = list(rows)
    for index, source in enumerate(input_rows):
        row = {str(k).strip().lower(): v for k, v in dict(source).items()}
        title = _normalized_text(_first(row, TITLE_KEYS))
        sold_date = _normalized_text(_first(row, DATE_KEYS))
        item_id = _stable_item_id(row)
        price = _parse_price(_first(row, PRICE_KEYS))
        currency = _normalized_text(_first(row, CURRENCY_KEYS) or "USD").upper()

        reasons: list[str] = []
        if not title:
            reasons.append("missing_title")
        if not sold_date:
            reasons.append("missing_sold_date")
        if price is None:
            reasons.append("invalid_or_ambiguous_price")
        if policy.require_item_id and not item_id:
            reasons.append("missing_item_id")
        if policy.require_usd and currency != "USD":
            reasons.append("non_usd_currency")

        sanitized = {
            "item_id": item_id,
            "title": title,
            "sold_date": sold_date,
            "sold_price": price,
            "currency": currency,
        }
        sanitized["fingerprint"] = _fingerprint(sanitized)

        if reasons:
            rejected.append({
                "row_index": index,
                "reasons": reasons,
                "sanitized": sanitized,
            })
            continue

        dedupe_key = item_id or sanitized["fingerprint"]
        if dedupe_key in seen:
            duplicates += 1
            continue
        seen.add(dedupe_key)
        accepted.append(sanitized)

    missing_required = sum(
        1
        for row in rejected
        if any(reason.startswith("missing_") for reason in row["reasons"])
    )
    missing_share = missing_required / len(input_rows) if input_rows else 0.0
    blockers: list[str] = []
    if not input_rows:
        blockers.append("empty_export")
    if missing_share > policy.max_missing_required_share:
        blockers.append("required_field_loss_exceeds_policy")

    manifest_payload = {
        "accepted": accepted,
        "rejected": rejected,
        "duplicates": duplicates,
        "input_rows": len(input_rows),
    }

    return {
        **manifest_payload,
        "accepted_rows": len(accepted),
        "rejected_rows": len(rejected),
        "missing_required_share": missing_share,
        "ready": not blockers,
        "blockers": blockers,
        "corpus_sha256": _fingerprint(manifest_payload),
        "sensitive_fields_removed": sorted(SENSITIVE_KEYS),
    }
