from typing import Optional
import requests
from .base import EvidenceRecord, ProviderResult
from .ebay_auth import EbayOAuthClient

SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

class EbayBrowseProvider:
    """Official eBay Browse API adapter for live marketplace supply/listing evidence."""
    provider_name = "ebay_browse"

    def __init__(self, oauth: Optional[EbayOAuthClient]=None, marketplace_id: str="EBAY_US", timeout: int=20):
        self.oauth=oauth or EbayOAuthClient()
        self.marketplace_id=marketplace_id
        self.timeout=timeout

    def _parse_response(self, data, query: str) -> ProviderResult:
        records=[]
        for item in data.get("itemSummaries",[]):
            p=item.get("price") or {}
            try: price=float(p.get("value"))
            except Exception: continue
            records.append(EvidenceRecord(
                provider=self.provider_name,
                record_type="active_listing",
                source_item_id=str(item.get("legacyItemId") or item.get("itemId") or ""),
                title=item.get("title") or "",
                price=price,
                currency=p.get("currency") or "USD",
                event_date=item.get("itemCreationDate"),
                url=item.get("itemWebUrl"),
                payload=item,
            ))
        return ProviderResult(records,query,self.provider_name,{
            "total":data.get("total"),"limit":data.get("limit"),"offset":data.get("offset"),"href":data.get("href")
        })

    def search_active(self, query: str, limit: int=50, category_id: Optional[str]=None, offset: int=0) -> ProviderResult:
        token=self.oauth.get_application_token()
        params={"q":query,"limit":min(max(limit,1),200),"offset":max(offset,0)}
        if category_id:
            params["category_ids"]=category_id
        headers={
            "Authorization":f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID":self.marketplace_id,
        }
        r=requests.get(SEARCH_URL,params=params,headers=headers,timeout=self.timeout)
        r.raise_for_status()
        return self._parse_response(r.json(),query)
