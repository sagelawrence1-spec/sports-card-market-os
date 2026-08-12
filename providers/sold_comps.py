"""Fail-closed adapter for SoldComps' public eBay sold-results API."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
import hashlib
import re
from typing import Iterable, Mapping, Optional

import requests

from .base import EvidenceRecord, ProviderResult


SALES_URL = "https://api.sold-comps.com/v1/scrape"


def _number(value) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    text=re.sub(r"[^0-9.\-]", "", str(value).replace(",", ""))
    if not text or text in {"-", "."}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _truthy(value) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes"}


def _normalized(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


class SoldCompsProvider:
    """Small-scale public sold-result evidence for the private alpha.

    The source is capped at evidence grade B. Best Offer transactions are
    excluded because eBay exposes the asking price, not the negotiated price.
    """

    provider_name="sold_comps"
    source_label="Public eBay sold-result evidence — Best Offers excluded"
    evidence_grade_cap="B"

    def __init__(
        self,
        api_key: str,
        *,
        ebay_site: str="ebay.com",
        timeout: int=20,
        max_queries_per_run: int=3,
        session=None,
    ):
        if not str(api_key or "").strip():
            raise ValueError("The SoldComps API key is required.")
        if max_queries_per_run < 1:
            raise ValueError("SoldComps max queries per run must be at least 1.")
        self.api_key=api_key.strip()
        self.ebay_site=ebay_site.strip() or "ebay.com"
        self.timeout=timeout
        self.max_queries_per_run=max_queries_per_run
        self.session=session or requests

    def plan_queries(self, assets: Iterable[Mapping], *, as_of: Optional[str]=None):
        """Group canonical cards and rotate groups through the free allowance."""
        groups=defaultdict(list)
        for asset in assets:
            key=tuple(_normalized(asset.get(field)).lower() for field in (
                "player", "year", "grade_company", "grade"
            ))
            groups[key].append(dict(asset))

        plans=[]
        for key in sorted(groups):
            player,year,grader,grade=key
            parts=[year,player,grader,grade,"-reprint","-lot","-break"]
            plans.append({
                "query":" ".join(part for part in parts if part),
                "assets":groups[key],
                "category_id":str(groups[key][0].get("ebay_category_id") or "261328"),
            })
        if len(plans) <= self.max_queries_per_run:
            return plans

        run_day=date.today()
        if as_of:
            try:
                run_day=datetime.fromisoformat(str(as_of).replace("Z","+00:00")).date()
            except ValueError:
                pass
        start=(run_day.toordinal()*self.max_queries_per_run) % len(plans)
        return [plans[(start+offset) % len(plans)] for offset in range(self.max_queries_per_run)]

    def _parse_response(self, data: Mapping, query: str) -> ProviderResult:
        records=[]
        exclusions=Counter()
        for item in data.get("items",[]):
            sold_price=_number(item.get("soldPrice"))
            shipping_price=_number(item.get("shippingPrice"))
            sold_currency=_normalized(item.get("soldCurrency")).upper()
            shipping_currency=_normalized(item.get("shippingCurrency")).upper()
            event_date=_normalized(item.get("endedAt"))
            listing_type=_normalized(item.get("listingType")).lower()
            reason=None

            if listing_type and listing_type!="sold":
                reason="not_a_sold_listing"
            elif _truthy(item.get("bestOfferAccepted")):
                reason="best_offer_price_is_upper_bound"
            elif sold_price is None or sold_price <= 0:
                reason="invalid_sold_price"
            elif sold_currency!="USD":
                reason="non_usd_currency"
            elif shipping_price is None:
                reason="shipping_price_unknown"
            elif shipping_price < 0:
                reason="invalid_shipping_price"
            elif shipping_price > 0 and shipping_currency not in {"USD"}:
                reason="shipping_currency_unknown_or_mismatched"
            else:
                try:
                    date.fromisoformat(event_date[:10])
                except ValueError:
                    reason="invalid_sale_date"

            title=_normalized(item.get("title"))
            item_id=_normalized(item.get("itemId"))
            if not title:
                reason=reason or "missing_title"
            if not item_id:
                reason=reason or "missing_source_id"

            price=round((sold_price or 0)+(shipping_price or 0),2)
            reported_total=_number(item.get("totalPrice"))
            if reason is None and reported_total is not None and abs(reported_total-price) > .02:
                reason="inconsistent_total_price"

            if reason:
                exclusions[reason]+=1
            payload=dict(item)
            payload.update({
                "source_platform":"eBay",
                "price_basis":"sold_price_plus_shipping",
                "normalized_sold_price":sold_price,
                "normalized_shipping_price":shipping_price,
                "policy_eligible":reason is None,
            })
            if reason:
                payload["policy_reason"]=reason
            if not item_id:
                fingerprint="|".join((title,event_date,str(sold_price),str(shipping_price)))
                item_id=f"missing-{hashlib.sha256(fingerprint.encode()).hexdigest()[:16]}"
            records.append(EvidenceRecord(
                provider=self.provider_name,
                record_type="sold",
                source_item_id=f"ebay:{item_id}",
                title=title,
                price=price,
                event_date=event_date or None,
                url=item.get("url"),
                currency=sold_currency or "UNKNOWN",
                payload=payload,
                policy_eligible=reason is None,
                policy_reason=reason,
            ))

        return ProviderResult(records,query,self.provider_name,{
            "page":data.get("page"),
            "total_items":data.get("totalItems"),
            "total_results":data.get("totalResults"),
            "has_next_page":data.get("hasNextPage"),
            "policy_exclusions":dict(exclusions),
        })

    def search_sold(
        self,
        query: str,
        *,
        limit: int=240,
        page: int=1,
        category_id: Optional[str]=None,
        date_from: Optional[str]=None,
        date_to: Optional[str]=None,
        **_kwargs,
    ) -> ProviderResult:
        params={
            "keyword":query,
            "ebaySite":self.ebay_site,
            "page":max(int(page),1),
            "count":min(max(int(limit),1),240),
            "sortOrder":"endedRecently",
            "sold":"true",
            "includeCompleteListing":"true",
        }
        if category_id:
            params["categoryId"]=str(category_id)
        if date_from:
            params["soldAfter"]=str(date_from)[:10]
        if date_to:
            params["soldBefore"]=str(date_to)[:10]
        response=self.session.get(
            SALES_URL,
            params=params,
            headers={"Authorization":f"Bearer {self.api_key}"},
            timeout=self.timeout,
        )
        if response.status_code==401:
            raise PermissionError("The SoldComps API key is missing or invalid.")
        if response.status_code in {403,429}:
            raise RuntimeError("The SoldComps request allowance is exhausted.")
        response.raise_for_status()
        result=self._parse_response(response.json(),query)
        result.metadata["rate_limit"]={
            "limit":response.headers.get("X-RateLimit-Limit"),
            "remaining":response.headers.get("X-RateLimit-Remaining"),
            "reset":response.headers.get("X-RateLimit-Reset"),
        }
        return result
