"""
Authoritative eBay Product Research ingestion boundary.

Product Research is eBay's own historical sales-data surface. eBay currently does not
publish an open Marketplace Insights endpoint for new users, so this adapter accepts
structured extracts captured from Product Research without changing downstream logic.

Accepted input: CSV with flexible aliases for title, sold price, sold date, item ID and URL.
"""
import csv, re
from pathlib import Path
from .base import EvidenceRecord, ProviderResult

ALIASES={
    "title":["title","item title","listing title"],
    "price":["sold price","sale price","price","final price"],
    "date":["sold date","sale date","date sold","date"],
    "id":["item id","itemid","listing id","ebay item id"],
    "url":["url","item url","listing url"],
    "currency":["currency","currency code"],
    "shipping":["shipping","shipping price","shipping cost"],
    "format":["listing format","format","sale type"],
}

def _norm(s): return re.sub(r"[^a-z0-9]+"," ",str(s).lower()).strip()

def _find(headers, aliases):
    nh={_norm(h):h for h in headers}
    for a in aliases:
        if _norm(a) in nh: return nh[_norm(a)]
    return None

def _money(v):
    s=re.sub(r"[^0-9.\-]","",str(v or ""))
    return float(s) if s else None

class EbayProductResearchProvider:
    provider_name="ebay_product_research"

    def load_csv(self,path: str, query: str="") -> ProviderResult:
        p=Path(path)
        with p.open(newline="",encoding="utf-8-sig") as f:
            rows=list(csv.DictReader(f))
        if not rows:
            return ProviderResult([],query,self.provider_name,{"path":str(p)})
        headers=list(rows[0].keys())
        cols={k:_find(headers,v) for k,v in ALIASES.items()}
        if not cols["title"] or not cols["price"]:
            raise ValueError(f"Could not locate title/price columns. Headers={headers}")
        records=[]
        for i,r in enumerate(rows,1):
            price=_money(r.get(cols["price"]))
            if price is None: continue
            sid=(r.get(cols["id"]) if cols["id"] else None) or f"row-{i}"
            currency=(r.get(cols["currency"]) if cols["currency"] else "USD") or "USD"
            shipping=_money(r.get(cols["shipping"])) if cols["shipping"] else None
            payload=dict(r)
            payload["normalized_shipping"] = shipping
            payload["normalized_listing_format"] = r.get(cols["format"]) if cols["format"] else None
            records.append(EvidenceRecord(
                provider=self.provider_name,record_type="sold",source_item_id=str(sid),
                title=r.get(cols["title"]) or "",price=price,
                event_date=(r.get(cols["date"]) if cols["date"] else None),
                url=(r.get(cols["url"]) if cols["url"] else None),currency=str(currency).upper(),payload=payload,
            ))
        return ProviderResult(records,query,self.provider_name,{"path":str(p),"rows":len(rows),"columns":cols})
