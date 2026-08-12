"""Licensed sold-transaction adapter for The Card API.

The provider is deliberately strict. A record can reach valuation only when its
price is confirmed, its currency provenance is trustworthy, and its price basis
is comparable with the other accepted observations. Ineligible records are
returned for audit persistence, but the pipeline rejects them before matching.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
import re
from typing import Iterable, Mapping, Optional

import requests

from .base import EvidenceRecord, ProviderResult


SALES_URL = "https://thecardapi.com/api/v1/market/sales"
DEFAULT_CURRENCY_TRUST_DATE = date(2026, 8, 1)


def _platform_slug(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _canonical_source_id(platform: str, value: object) -> str:
    raw = str(value or "").strip()
    slug = _platform_slug(platform) or "unknown"
    lowered = raw.lower()
    for prefix in (f"{slug}-", f"{slug}:"):
        if lowered.startswith(prefix):
            raw = raw[len(prefix):]
            break
    return f"{slug}:{raw}" if raw else f"{slug}:missing"


class TheCardApiSoldProvider:
    """Confirmed sold evidence accessed under The Card API's paid-plan terms."""

    provider_name = "the_card_api"
    source_label = "Licensed confirmed marketplace sales"

    def __init__(
        self,
        api_key: str,
        *,
        platforms: Iterable[str] = ("ebay",),
        timeout: int = 20,
        min_currency_trust_date: date = DEFAULT_CURRENCY_TRUST_DATE,
        goldin_buyer_premium: Optional[float] = None,
        session=None,
    ):
        if not str(api_key or "").strip():
            raise ValueError("The Card API key is required.")
        normalized = tuple(dict.fromkeys(_platform_slug(value) for value in platforms if value))
        if not normalized:
            raise ValueError("At least one sold-data platform must be configured.")
        if goldin_buyer_premium is not None and not 0 <= goldin_buyer_premium <= 1:
            raise ValueError("Goldin buyer premium must be a decimal between 0 and 1.")
        self.api_key = api_key.strip()
        self.platforms = normalized
        self.timeout = timeout
        self.min_currency_trust_date = min_currency_trust_date
        self.goldin_buyer_premium = goldin_buyer_premium
        self.session = session or requests

    def _parse_response(self, data: Mapping, query: str) -> ProviderResult:
        records = []
        exclusions = Counter()
        for item in data.get("data", []):
            platform = str(item.get("platform") or "").strip()
            platform_slug = _platform_slug(platform)
            raw_price = item.get("price")
            try:
                price = float(raw_price)
            except (TypeError, ValueError):
                price = 0.0

            sale_date = str(item.get("sale_date") or item.get("sold_at") or "").strip()
            currency = str(item.get("currency") or "").strip().upper()
            reason = None
            price_basis = "reported_final_price"

            if platform_slug not in self.platforms:
                reason = "platform_not_enabled"
            elif item.get("price_confirmed") is not True:
                reason = "price_not_confirmed"
            elif price <= 0:
                reason = "invalid_price"
            elif currency != "USD":
                reason = "non_usd_currency"
            else:
                try:
                    sold_day = date.fromisoformat(sale_date[:10])
                except ValueError:
                    reason = "invalid_sale_date"
                else:
                    if sold_day < self.min_currency_trust_date:
                        reason = "historical_currency_provenance_untrusted"

            if platform_slug == "goldin":
                if self.goldin_buyer_premium is None:
                    reason = reason or "unnormalized_hammer_price"
                    price_basis = "hammer_price"
                elif reason is None:
                    price = round(price * (1 + self.goldin_buyer_premium), 2)
                    price_basis = "hammer_plus_configured_buyer_premium"

            title = str(item.get("title") or "").strip()
            if not title:
                reason = reason or "missing_title"

            source_item_id = _canonical_source_id(platform, item.get("id"))
            if source_item_id.endswith(":missing"):
                reason = reason or "missing_source_id"

            if reason:
                exclusions[reason] += 1
            payload = dict(item)
            payload["source_platform"] = platform
            payload["price_basis"] = price_basis
            payload["policy_eligible"] = reason is None
            if reason:
                payload["policy_reason"] = reason
            records.append(EvidenceRecord(
                provider=self.provider_name,
                record_type="sold",
                source_item_id=source_item_id,
                title=title,
                price=price,
                event_date=sale_date or None,
                url=item.get("listing_url"),
                currency=currency or "UNKNOWN",
                payload=payload,
                policy_eligible=reason is None,
                policy_reason=reason,
            ))

        pagination = dict(data.get("pagination") or {})
        return ProviderResult(records, query, self.provider_name, {
            "total": pagination.get("total"),
            "limit": pagination.get("limit"),
            "next_cursor": pagination.get("next_cursor"),
            "coverage": dict(data.get("meta") or {}),
            "policy_exclusions": dict(exclusions),
        })

    def search_sold(
        self,
        query: str,
        *,
        limit: int = 200,
        asset: Optional[Mapping] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        **_kwargs,
    ) -> ProviderResult:
        all_records = []
        exclusions = Counter()
        responses = []
        rate_limit = {}
        for platform in self.platforms:
            params = {
                "q": query,
                "platform": platform,
                "limit": min(max(int(limit), 1), 1000),
                "sort": "date_desc",
            }
            # The provider documents category coverage for recent eBay rows;
            # auction-house category fields are still awaiting backfill.
            if platform == "ebay":
                params["category"] = "sports"
            if date_from:
                params["date_from"] = date_from
            if date_to:
                params["date_to"] = date_to
            if asset:
                grader = str(asset.get("grade_company") or "").strip()
                grade = str(asset.get("grade") or "").replace(".0", "").strip()
                if grader:
                    params["graded"] = "true"
                    params["grader"] = grader
                if grader and grade:
                    params["grade"] = grade

            response = self.session.get(
                SALES_URL,
                params=params,
                headers={"x-market-api-key": self.api_key},
                timeout=self.timeout,
            )
            if response.status_code in {401, 403}:
                raise PermissionError("The Card API key or plan does not permit this sold-data request.")
            if response.status_code == 429:
                raise RuntimeError("The Card API daily sales allowance is exhausted.")
            response.raise_for_status()
            parsed = self._parse_response(response.json(), query)
            all_records.extend(parsed.records)
            exclusions.update(parsed.metadata.get("policy_exclusions") or {})
            responses.append(parsed.metadata)
            rate_limit = {
                "limit": response.headers.get("X-RateLimit-Limit"),
                "remaining": response.headers.get("X-RateLimit-Remaining"),
                "reset": response.headers.get("X-RateLimit-Reset"),
            }

        return ProviderResult(all_records, query, self.provider_name, {
            "platforms": list(self.platforms),
            "responses": responses,
            "policy_exclusions": dict(exclusions),
            "rate_limit": rate_limit,
        })
