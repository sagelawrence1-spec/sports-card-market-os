from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
from typing import Any, Iterable, Mapping

from providers.ebay_product_research import (
    _canonical_item_id,
    _currency as _provider_currency,
    _currency_conflicts,
    _item_id_from_url,
    _money,
    _shipping_amount,
    _sold_quantity,
)


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
URL_KEYS = ("url", "item_url", "listing_url")
TITLE_KEYS = ("title", "item_title", "listing_title")
PRICE_KEYS = ("sold_price", "price", "sale_price")
DATE_KEYS = ("sold_date", "date_sold", "sale_date", "end_date")
CURRENCY_KEYS = ("currency", "currency_code")
SHIPPING_KEYS = ("shipping", "shipping_price", "shipping_cost")
QUANTITY_KEYS = ("quantity", "qty", "sold_quantity")

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
    require_shipping: bool = True
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


def _resolve_item_id(row: Mapping[str, Any]) -> tuple[str | None, list[str]]:
    """Mirror production Product Research identity validation.

    Explicit IDs must be canonical numeric eBay item IDs. Any supplied URL must itself
    resolve to an eBay item URL, even when an explicit item ID is also present. This keeps
    proof intake from admitting evidence that the authoritative production provider rejects.
    Contradictory explicit/URL identities fail closed instead of being normalized into one
    proof record.
    """
    reasons: list[str] = []
    raw_explicit_id = _first(row, ID_KEYS)
    explicit_text = _normalized_text(raw_explicit_id)
    explicit_id = _canonical_item_id(explicit_text)
    if explicit_text and explicit_id is None:
        reasons.append("invalid_item_id")

    raw_url = _first(row, URL_KEYS)
    raw_url_text = _normalized_text(raw_url)
    url_id = _item_id_from_url(raw_url)
    if raw_url_text and url_id is None:
        reasons.append("invalid_item_url")
    if explicit_id and url_id and explicit_id != url_id:
        reasons.append("conflicting_item_id")

    return explicit_id or url_id, reasons


def _fingerprint(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sanitize_product_research_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    policy: CorpusIntakePolicy | None = None,
) -> dict[str, Any]:
    """Normalize Product Research rows using the production provider's evidence rules.

    The proof corpus must not admit evidence the authoritative production provider would
    reject. Monetary parsing, currency conflicts, shipping, quantity and sold-item identity
    therefore share the provider helpers, and accepted comps use the same
    sold-price-plus-shipping valuation basis.
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
        item_id, identity_reasons = _resolve_item_id(row)
        raw_price = _first(row, PRICE_KEYS)
        sold_price = _money(raw_price)
        explicit_currency = _first(row, CURRENCY_KEYS)
        currency = _provider_currency(explicit_currency, raw_price)
        raw_shipping = _first(row, SHIPPING_KEYS)
        shipping = _shipping_amount(raw_shipping)
        quantity_key_present = any(key in row for key in QUANTITY_KEYS)
        raw_quantity = _first(row, QUANTITY_KEYS)
        quantity = _sold_quantity(raw_quantity) if quantity_key_present else None

        reasons: list[str] = list(identity_reasons)
        if not title:
            reasons.append("missing_title")
        if raw_sold_date in (None, ""):
            reasons.append("missing_sold_date")
        elif sold_date is None:
            reasons.append("invalid_sold_date")
        if _currency_conflicts(currency, raw_price):
            reasons.append("conflicting_currency_evidence")
        if sold_price is None:
            reasons.append("invalid_or_ambiguous_price")
        if policy.require_item_id and not item_id:
            reasons.append("missing_stable_item_id")
        if policy.require_usd and currency is None:
            reasons.append("missing_currency")
        elif policy.require_usd and currency != "USD":
            reasons.append("non_usd_currency")
        if policy.require_shipping and raw_shipping in (None, ""):
            reasons.append("missing_shipping")
        elif raw_shipping not in (None, "") and _currency_conflicts(currency, raw_shipping):
            reasons.append("conflicting_shipping_currency")
        elif policy.require_shipping and shipping is None:
            reasons.append("invalid_or_missing_shipping")
        if quantity_key_present:
            if quantity is None:
                reasons.append("invalid_or_missing_quantity")
            elif quantity != 1:
                reasons.append("multi_unit_sale")

        landed_price = None
        if sold_price is not None and shipping is not None:
            landed_price = round(sold_price + shipping, 2)

        sanitized = {
            "item_id": item_id,
            "title": title,
            "sold_date": sold_date,
            "sold_price": sold_price,
            "shipping": shipping,
            "landed_price": landed_price,
            "price_basis": "sold_price_plus_shipping" if landed_price is not None else None,
            "currency": currency,
            "quantity": quantity,
        }
        sanitized["fingerprint"] = _fingerprint(sanitized)

        if reasons:
            rejected.append({
                "row_index": index,
                "reasons": reasons,
                "sanitized": sanitized,
            })
            continue

        # Product Research can report multiple transactions from one multi-quantity
        # listing. Match production identity at the available day granularity.
        dedupe_key = f"{item_id}:{sold_date}" if item_id else sanitized["fingerprint"]
        prior_fingerprint = seen_fingerprints_by_key.get(dedupe_key)
        if prior_fingerprint is not None:
            if prior_fingerprint == sanitized["fingerprint"]:
                duplicates += 1
            else:
                conflicting_duplicates += 1
                rejected.append({
                    "row_index": index,
                    "reasons": ["conflicting_duplicate_evidence"],
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
