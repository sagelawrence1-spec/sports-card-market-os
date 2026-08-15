"""
Authoritative eBay Product Research ingestion boundary.

Product Research is eBay's own historical sales-data surface. eBay currently does not
publish an open Marketplace Insights endpoint for new users, so this adapter accepts
structured extracts captured from Product Research without changing downstream logic.

Accepted input: CSV with flexible aliases for title, sold price, sold date, item ID and URL.
Rows fail closed when sold date, price, USD currency evidence, or stable sold-item identity
is ambiguous.
"""
import csv, re
from collections import Counter
from datetime import datetime
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

_SOLD_DATE_FORMATS=("%Y-%m-%d","%m/%d/%Y","%m/%d/%y","%b %d, %Y","%B %d, %Y")
_PRICE_RANGE_RE=re.compile(r"\d[\d,.]*\s*[-–—]\s*[$€£]?\s*\d[\d,.]*")
_EBAY_ITEM_URL_RE=re.compile(r"/itm/(?:[^/?#]+/)?(\d+)(?:[/?#]|$)",re.IGNORECASE)

def _norm(s): return re.sub(r"[^a-z0-9]+"," ",str(s).lower()).strip()

def _find(headers, aliases):
    nh={_norm(h):h for h in headers}
    for a in aliases:
        if _norm(a) in nh: return nh[_norm(a)]
    return None

def _money(v):
    text=" ".join(str(v or "").strip().split())
    if not text or _PRICE_RANGE_RE.search(text): return None
    s=re.sub(r"[^0-9.]","",text.replace(",",""))
    if not s or s.count(".")>1: return None
    try: value=float(s)
    except ValueError: return None
    return value if value>0 else None

def _sold_date(v):
    text=" ".join(str(v or "").strip().split())
    if not text: return None
    for fmt in _SOLD_DATE_FORMATS:
        try: return datetime.strptime(text,fmt).date().isoformat()
        except ValueError: continue
    return None

def _currency(explicit, raw_price):
    value=" ".join(str(explicit or "").strip().split()).upper()
    if value: return value
    price_text=" ".join(str(raw_price or "").strip().split())
    upper=price_text.upper()
    if "$" in price_text and "CAD" not in upper and "AUD" not in upper:
        return "USD"
    return None

def _item_id_from_url(v):
    text=str(v or "").strip()
    if not text: return None
    match=_EBAY_ITEM_URL_RE.search(text)
    return match.group(1) if match else None

class EbayProductResearchProvider:
    provider_name="ebay_product_research"

    def load_csv(self,path: str, query: str="") -> ProviderResult:
        p=Path(path)
        with p.open(newline="",encoding="utf-8-sig") as f:
            rows=list(csv.DictReader(f))
        if not rows:
            return ProviderResult([],query,self.provider_name,{"path":str(p),"rows":0,"accepted_rows":0,"rejected_rows":0,"rejection_reasons":{}})
        headers=list(rows[0].keys())
        cols={k:_find(headers,v) for k,v in ALIASES.items()}
        if not cols["title"] or not cols["price"] or not cols["date"]:
            raise ValueError(f"Could not locate title/price/date columns. Headers={headers}")
        records=[]
        rejection_reasons=Counter()
        for r in rows:
            raw_price=r.get(cols["price"])
            price=_money(raw_price)
            sold_date=_sold_date(r.get(cols["date"]))
            explicit_currency=r.get(cols["currency"]) if cols["currency"] else None
            currency=_currency(explicit_currency,raw_price)
            if price is None:
                rejection_reasons["invalid_or_ambiguous_price"]+=1
                continue
            if sold_date is None:
                rejection_reasons["invalid_sold_date"]+=1
                continue
            if currency is None:
                rejection_reasons["missing_currency"]+=1
                continue
            if currency!="USD":
                rejection_reasons["non_usd_currency"]+=1
                continue
            explicit_id=str(r.get(cols["id"]) or "").strip() if cols["id"] else ""
            raw_url=r.get(cols["url"]) if cols["url"] else None
            url_id=_item_id_from_url(raw_url)
            if explicit_id and url_id and explicit_id!=url_id:
                rejection_reasons["conflicting_item_id"]+=1
                continue
            sid=explicit_id or url_id
            if not sid:
                rejection_reasons["missing_stable_item_id"]+=1
                continue
            shipping=_money(r.get(cols["shipping"])) if cols["shipping"] else None
            payload=dict(r)
            payload["normalized_shipping"] = shipping
            payload["normalized_listing_format"] = r.get(cols["format"]) if cols["format"] else None
            records.append(EvidenceRecord(
                provider=self.provider_name,record_type="sold",source_item_id=sid,
                title=r.get(cols["title"]) or "",price=price,
                event_date=sold_date,
                url=raw_url,currency=currency,payload=payload,
            ))
        return ProviderResult(records,query,self.provider_name,{
            "path":str(p),"rows":len(rows),"columns":cols,
            "accepted_rows":len(records),"rejected_rows":len(rows)-len(records),
            "rejection_reasons":dict(sorted(rejection_reasons.items())),
        })