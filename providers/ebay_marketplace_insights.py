from typing import Optional

import requests

from .base import EvidenceRecord, ProviderResult
from .ebay_auth import EbayOAuthClient


SEARCH_URL="https://api.ebay.com/buy/marketplace_insights/v1_beta/item_sales/search"
INSIGHTS_SCOPE="https://api.ebay.com/oauth/api_scope/buy.marketplace.insights"

class EbayMarketplaceInsightsProvider:
    """Boundary for eBay's official sold-history API.

    eBay documents Marketplace Insights as Limited Release and restricted to existing
    approved users. Keeping this interface explicit lets the MVP switch to it without
    changing normalization/scoring once access is available.
    """
    provider_name="ebay_marketplace_insights"

    def __init__(self, oauth: Optional[EbayOAuthClient]=None, marketplace_id: str="EBAY_US", timeout: int=20):
        self.oauth=oauth or EbayOAuthClient()
        self.marketplace_id=marketplace_id
        self.timeout=timeout

    def _parse_response(self, data, query: str) -> ProviderResult:
        records=[]
        for item in data.get("itemSales",[]):
            price_data=item.get("lastSoldPrice") or item.get("price") or {}
            try: price=float(price_data.get("value"))
            except Exception: continue
            item_id=str(item.get("legacyItemId") or item.get("itemId") or "")
            records.append(EvidenceRecord(
                provider=self.provider_name,
                record_type="sold",
                source_item_id=item_id,
                title=item.get("title") or "",
                price=price,
                currency=price_data.get("currency") or "USD",
                event_date=item.get("lastSoldDate") or item.get("itemSoldDate"),
                url=item.get("itemWebUrl"),
                payload=item,
            ))
        return ProviderResult(records,query,self.provider_name,{
            "total":data.get("total"),"limit":data.get("limit"),"offset":data.get("offset"),
            "href":data.get("href"),"next":data.get("next")
        })

    def search_sold(self, query: str, limit: int=50, category_id: str="261328", offset: int=0, **kwargs) -> ProviderResult:
        token=self.oauth.get_application_token(INSIGHTS_SCOPE)
        params={
            "q":query,
            "category_ids":category_id,
            "limit":min(max(limit,1),200),
            "offset":max(offset,0),
        }
        headers={
            "Authorization":f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID":self.marketplace_id,
        }
        r=requests.get(SEARCH_URL,params=params,headers=headers,timeout=self.timeout)
        if r.status_code in {401,403}:
            raise PermissionError(
                "eBay Marketplace Insights access is not enabled for this application. "
                "The buy.marketplace.insights scope requires eBay partner approval."
            )
        r.raise_for_status()
        return self._parse_response(r.json(),query)
