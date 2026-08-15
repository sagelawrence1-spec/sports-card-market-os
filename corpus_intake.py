from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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

_PRICE_RANGE_RE = re.compile(r"\d[\d,.]*\s*[-–—]\s*[$€£]?\s*\d[\d,.]*")
_HEADER_SEP_RE = re.compile(r"[^a-z0-9]+")
_SOLD_DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%b %d, %Y",
    "%B %d, %Y",
)


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


def _normalized_header(value: Any) -> str:
    """Canonicalize export headers across CSV/TSV spelling and spacing variants."""
    text = str(value or "").strip().lower()
    return _HEADER_SEP_RE.sub("_", text).strip("_")


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


def _parse_sold_date(value: Any) -> str | None:
    text = _normalized_text(value)
    if not text:
        return None
    for fmt in _SOLD_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _currency(row: Mapping[str, Any], raw_price: Any) -> str | None:
    explicit = _normalized_text(_first(row, CURRENCY_KEYS)).upper()
    if explicit:
        return explicit
    price_text = _normalized_text(raw_price)
    if "$" in price_text and "CAD" not in price_text.upper() and "AUD" not in price_text.upper():
        return "USD"
    return None


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
    Seller/buyer contact fields are removed. Ambiguous prices, malformed sold dates,
    unknown currency, missing core fields, conflicting duplicate item IDs, and non-USD
    rows (by default) fail closed instead of being silently coerced into usable evidence.
    """
    policy = policy or CorpusIntakePolicy()
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_fingerprints_by_key: dict[str, str] = {}
    duplicates = 0
    conflicting_duplicates = 0

    input_rows = list(rows)
    for index, source in enumerate(input_rows):
        row = {_normalized_header(k): v for k, v in dict(source).items()}
        title = _normalized_text(_first(row, TITLE_KEYS))
        raw_sold_date = _first(row, DATE_KEYS)
        sold_date = _parse_sold_date(raw_sold_date)
        item_id = _stable_item_id(row)
        raw_price = _first(row, PRICE_KEYS)
        price = _parse_price(raw_price)
        currency = _currency(row, raw_price)

        reasons: list[str] = []
        if not title:
            reasons.append("missing_title")
        if raw_sold_date in (None, ""):
            reasons.append("missing_sold_date")
        elif sold_date is None:
            reasons.append("invalid_sold_date")
        if price is None:
            reasons.append("invalid_or_ambiguous_price")
        if policy.require_item_id and not item_id:
            reasons.append("missing_item_id")
        if policy.require_usd and currency is None:
            reasons.append("missing_currency")
        elif policy.require_usd and currency != "USD":
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
        prior_fingerprint = seen_fingerprints_by_key.get(dedupe_key)
        if prior_fingerprint is not None:
            if prior_fingerprint == sanitized["fingerprint"]:
                duplicates += 1
            else:
                conflicting_duplicates += 1
                rejected.append({
                    "row_index": index,
                    "reasons": ["conflicting_duplicate_item_id"],
                    "sanitized": sanitized,
                })
            continue

        seen_fingerprints_by_key[dedupe_key] = sanitized["fingerprint"]
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
    if conflicting_duplicates:
        blockers.append("conflicting_duplicate_evidence")

    manifest_payload = {
        "accepted": accepted,
        "rejected": rejected,
        "duplicates": duplicates,
        "conflicting_duplicates": conflicting_duplicates,
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
