"""Official eBay Product Research structured-ingestion boundary.

Product Research is eBay's own historical sales-data surface and reports the actual sold
price, including accepted Best Offers. This parser accepts CSV/TSV extracts or copied table
exports with flexible column names. It does not scrape eBay or store account credentials.
"""
import csv, re, hashlib
from pathlib import Path
from dateutil import parser as dtparser
from .base import EvidenceRecord, ProviderResult

ALIASES={
    "title":["title","item title","listing title","item"],
    "price":["sold price","sale price","price","final price","average sold price"],
    "date":["sold date","sale date","date sold","date","transaction date"],
    "id":["item id","itemid","listing id","ebay item id","item number"],
    "url":["url","item url","listing url","view item"],
    "shipping":["shipping","shipping cost","shipping price"],
    "currency":["currency","currency code"],
    "format":["format","listing format","selling format"],
}

def _norm(s): return re.sub(r"[^a-z0-9]+"," ",str(s).lower()).strip()

def _find(headers, aliases):
    nh={_norm(h):h for h in headers}
    for a in aliases:
        if _norm(a) in nh: return nh[_norm(a)]
    return None

def _money(v):
    s=str(v or '').strip()
    neg=s.startswith('(') and s.endswith(')')
    nums=re.findall(r"-?\d[\d,]*(?:\.\d+)?",s)
    if len(nums) != 1:
        return None
    try:
        x=float(nums[0].replace(',',''))
    except (TypeError,ValueError):
        return None
    return -abs(x) if neg else x

def _date(v):
    if not v: return None
    try: return dtparser.parse(str(v),fuzzy=True).date().isoformat()
    except Exception: return str(v).strip()

def _currency(v, raw_price):
    if v: return str(v).strip().upper()
    s=str(raw_price or '').upper()
    if 'CAD' in s or 'C$' in s: return 'CAD'
    if 'GBP' in s or '£' in s: return 'GBP'
    if 'EUR' in s or '€' in s: return 'EUR'
    return 'USD'

class EbayProductResearchProvider:
    provider_name="ebay_product_research"

    def load_csv(self,path: str, query: str="") -> ProviderResult:
        p=Path(path)
        sample=p.read_text(encoding='utf-8-sig',errors='replace')[:8192]
        try: dialect=csv.Sniffer().sniff(sample,delimiters=',\t;|')
        except Exception: dialect=csv.excel
        with p.open(newline="",encoding="utf-8-sig",errors='replace') as f:
            rows=list(csv.DictReader(f,dialect=dialect))
        if not rows: return ProviderResult([],query,self.provider_name,{"path":str(p)})
        headers=list(rows[0].keys())
        cols={k:_find(headers,v) for k,v in ALIASES.items()}
        if not cols["title"] or not cols["price"]:
            raise ValueError(f"Could not locate title/price columns. Headers={headers}")
        records=[]
        for i,r in enumerate(rows,1):
            raw_price=r.get(cols['price']); price=_money(raw_price)
            if price is None or price <= 0: continue
            sid=(r.get(cols["id"]) if cols["id"] else None)
            if not sid:
                identity='|'.join([
                    str(r.get(cols["title"]) or '').strip(),
                    str(_date(r.get(cols["date"]) if cols["date"] else None) or ''),
                    f"{price:.2f}",
                    str(r.get(cols["url"]) if cols["url"] else '').strip(),
                ])
                sid='synthetic-'+hashlib.sha256(identity.encode('utf-8')).hexdigest()[:20]
            payload=dict(r)
            if cols.get('shipping'):
                payload['_parsed_shipping']=_money(r.get(cols['shipping']))
            if cols.get('format'):
                payload['_selling_format']=r.get(cols['format'])
            records.append(EvidenceRecord(
                provider=self.provider_name,record_type="sold",source_item_id=str(sid),
                title=r.get(cols["title"]) or "",price=price,
                currency=_currency(r.get(cols['currency']) if cols.get('currency') else None,raw_price),
                event_date=_date(r.get(cols["date"]) if cols["date"] else None),
                url=(r.get(cols["url"]) if cols["url"] else None),payload=payload,
            ))
        return ProviderResult(records,query,self.provider_name,{"path":str(p),"rows":len(rows),"columns":cols,"delimiter":getattr(dialect,'delimiter',',')})
