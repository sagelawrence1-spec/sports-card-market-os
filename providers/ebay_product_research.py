"""
Authoritative eBay Product Research ingestion boundary.

Product Research is eBay's own historical sales-data surface. eBay currently does not
publish an open Marketplace Insights endpoint for new users, so this adapter accepts
structured extracts captured from Product Research without changing downstream logic.

Accepted input: CSV with flexible aliases for title, sold price, sold date, item ID, URL,
and shipping. Rows fail closed when title, sold date, price, USD currency evidence,
stable sold-item identity, an explicitly exported shipping amount, quantity, or duplicate
sold evidence is ambiguous. Shipping provenance is required so authoritative comps always
share the same landed-price basis. Explicit multi-unit sales and explicit multi-card lots
are rejected so bundled transactions cannot masquerade as one single-card comp.
"""
import csv, re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from .base import EvidenceRecord, ProviderResult

ALIASES={
    "title":["title","item title","listing title"],
    "price":["sold price","sale price","price","final price","sold for"],
    "date":["sold date","sale date","date sold","date"],
    "id":["item id","itemid","listing id","ebay item id","item number"],
    "url":["url","item url","listing url"],
    "currency":["currency","currency code"],
    "shipping":["shipping","shipping price","shipping cost","shipping and handling"],
    "format":["listing format","format","sale type","selling format"],
    "quantity":["quantity","qty","sold quantity"],
}

_SOLD_DATE_FORMATS=("%Y-%m-%d","%m/%d/%Y","%m/%d/%y","%b %d, %Y","%B %d, %Y")
_PRICE_RANGE_RE=re.compile(r"\d[\d,.]*\s*[-–—]\s*[$€£]?\s*\d[\d,.]*")
_MONEY_VALUE_RE=re.compile(r"^(?:[A-Z]{3}\s*)?[$€£]?\s*(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?$",re.IGNORECASE)
_EBAY_ITEM_URL_RE=re.compile(r"/itm/(?:[^/?#]+/)?(\d+)(?:[/?#]|$)",re.IGNORECASE)
_CURRENCY_CODE_PREFIX_RE=re.compile(r"^([A-Z]{3})\b",re.IGNORECASE)
_MULTI_CARD_TITLE_PATTERNS=(
    re.compile(r"\b(?:lot|bundle)\b"),
    re.compile(r"\blot of (?:[2-9]|[1-9]\d+)\b"),
    re.compile(r"\b(?:[2-9]|[1-9]\d+) cards? lot\b"),
    re.compile(r"\b(?:[2-9]|[1-9]\d+) cards? bundle\b"),
    re.compile(r"\bbundle of (?:[2-9]|[1-9]\d+) cards?\b"),
    re.compile(r"\bset of (?:[2-9]|[1-9]\d+) cards?\b"),
    re.compile(r"\b(?:[2-9]|[1-9]\d+) cards? set\b"),
    re.compile(r"\bpair of cards?\b"),
    re.compile(r"\b(?:[2-9]|[1-9]\d+) cards? pack\b"),
    re.compile(r"\bpack of (?:[2-9]|[1-9]\d+) cards?\b"),
    re.compile(r"\b(?:two|three|four|five|six|seven|eight|nine|ten) cards? (?:lot|bundle|set|pack)\b"),
    re.compile(r"\b(?:lot|bundle|set|pack) of (?:two|three|four|five|six|seven|eight|nine|ten) cards?\b"),
)

def _norm(s): return re.sub(r"[^a-z0-9]+"," ",str(s).lower()).strip()

def _find(headers, aliases):
    nh={_norm(h):h for h in headers}
    for a in aliases:
        if _norm(a) in nh: return nh[_norm(a)]
    return None

def _title_indicates_multi_card_lot(title):
    normalized=_norm(title)
    return any(pattern.search(normalized) for pattern in _MULTI_CARD_TITLE_PATTERNS)

def _negative_money(text):
    stripped=" ".join(str(text or "").strip().split())
    if re.fullmatch(r"\(\s*(?:[A-Z]{3}\s*)?[$€£]?\s*\d[\d,.]*\s*\)",stripped,re.IGNORECASE):
        return True
    cleaned=re.sub(r"^(?:[A-Z]{3}\s*)?", "", stripped, flags=re.IGNORECASE)
    cleaned=re.sub(r"^([$€£])\s*", "", cleaned)
    if cleaned.startswith("-"):
        cleaned=cleaned[1:].lstrip()
        cleaned=re.sub(r"^([$€£])\s*", "", cleaned)
        return bool(re.match(r"\d",cleaned))
    return False

def _parsed_money_value(v):
    text=" ".join(str(v or "").strip().split())
    if not text or _PRICE_RANGE_RE.search(text) or _negative_money(text): return None
    if not _MONEY_VALUE_RE.fullmatch(text): return None
    numeric=re.sub(r"^(?:[A-Z]{3}\s*)?[$€£]?\s*", "", text, flags=re.IGNORECASE).replace(",","")
    try: return float(numeric)
    except ValueError: return None

def _money(v):
    value=_parsed_money_value(v)
    return value if value is not None and value>0 else None

def _shipping_amount(v):
    text=" ".join(str(v or "").strip().split())
    if not text: return None
    if text.lower() in {"free","free shipping"}: return 0.0
    value=_parsed_money_value(text)
    return value if value is not None and value>=0 else None

def _sold_quantity(v):
    text=" ".join(str(v or "").strip().split())
    if not text or not text.isdigit(): return None
    quantity=int(text)
    return quantity if quantity>0 else None

def _sold_date(v):
    text=" ".join(str(v or "").strip().split())
    if not text: return None
    for fmt in _SOLD_DATE_FORMATS:
        try: return datetime.strptime(text,fmt).date().isoformat()
        except ValueError: continue
    return None

def _strong_currency_marker(raw):
    """Return a currency only when the raw amount carries an unambiguous marker."""
    text=" ".join(str(raw or "").strip().split())
    upper=text.upper()
    if "€" in text: return "EUR"
    if "£" in text: return "GBP"
    code_match=_CURRENCY_CODE_PREFIX_RE.match(upper)
    if code_match:
        return code_match.group(1)
    for pattern,code in ((r"C\s*\$","CAD"),(r"A\s*\$","AUD"),(r"NZ\s*\$","NZD"),(r"HK\s*\$","HKD")):
        if re.search(pattern,upper): return code
    return None

def _currency_conflicts(currency, raw_amount):
    marker=_strong_currency_marker(raw_amount)
    return bool(currency and marker and marker!=currency)

def _currency(explicit, raw_price):
    value=" ".join(str(explicit or "").strip().split()).upper()
    if value: return value
    marker=_strong_currency_marker(raw_price)
    if marker:
        return marker
    price_text=" ".join(str(raw_price or "").strip().split())
    upper=price_text.upper()
    if "$" not in price_text:
        return None
    if re.search(r"[A-Z]",upper):
        return None
    return "USD"

def _canonical_item_id(v):
    text=str(v or "").strip()
    return text if text.isdigit() else None

def _item_id_from_url(v):
    text=str(v or "").strip()
    if not text: return None
    try:
        parsed=urlsplit(text)
    except ValueError:
        return None
    host=(parsed.hostname or "").lower().rstrip(".")
    if host!="ebay.com" and not host.endswith(".ebay.com"):
        return None
    match=_EBAY_ITEM_URL_RE.search(parsed.path)
    return match.group(1) if match else None

class EbayProductResearchProvider:
    provider_name="ebay_product_research"

    def load_csv(self,path: str, query: str="") -> ProviderResult:
        p=Path(path)
        with p.open(newline="",encoding="utf-8-sig") as f:
            rows=list(csv.DictReader(f))
        if not rows:
            return ProviderResult([],query,self.provider_name,{"path":str(p),"rows":0,"accepted_rows":0,"deduplicated_rows":0,"rejected_rows":0,"rejection_reasons":{}})
        headers=list(rows[0].keys())
        cols={k:_find(headers,v) for k,v in ALIASES.items()}
        if not cols["title"] or not cols["price"] or not cols["date"] or not cols["shipping"]:
            raise ValueError(f"Could not locate required title/price/date/shipping columns. Headers={headers}")
        candidates=[]
        rejection_reasons=Counter()
        for r in rows:
            title=" ".join(str(r.get(cols["title"]) or "").strip().split())
            raw_price=r.get(cols["price"])
            sold_price=_money(raw_price)
            sold_date=_sold_date(r.get(cols["date"]))
            explicit_currency=r.get(cols["currency"]) if cols["currency"] else None
            currency=_currency(explicit_currency,raw_price)
            if not title:
                rejection_reasons["missing_title"]+=1
                continue
            if _title_indicates_multi_card_lot(title):
                rejection_reasons["multi_card_lot"]+=1
                continue
            if cols["quantity"]:
                quantity=_sold_quantity(r.get(cols["quantity"]))
                if quantity is None:
                    rejection_reasons["invalid_or_missing_quantity"]+=1
                    continue
                if quantity!=1:
                    rejection_reasons["multi_unit_sale"]+=1
                    continue
            else:
                quantity=None
            if _currency_conflicts(currency,raw_price):
                rejection_reasons["conflicting_currency_evidence"]+=1
                continue
            if sold_price is None:
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
            raw_explicit_id=str(r.get(cols["id"]) or "").strip() if cols["id"] else ""
            explicit_id=_canonical_item_id(raw_explicit_id)
            if raw_explicit_id and explicit_id is None:
                rejection_reasons["invalid_item_id"]+=1
                continue
            raw_url=r.get(cols["url"]) if cols["url"] else None
            raw_url_text=str(raw_url or "").strip()
            url_id=_item_id_from_url(raw_url)
            if raw_url_text and not url_id:
                rejection_reasons["invalid_item_url"]+=1
                continue
            if explicit_id and url_id and explicit_id!=url_id:
                rejection_reasons["conflicting_item_id"]+=1
                continue
            sid=explicit_id or url_id
            if not sid:
                rejection_reasons["missing_stable_item_id"]+=1
                continue
            raw_shipping=r.get(cols["shipping"])
            if _currency_conflicts(currency,raw_shipping):
                rejection_reasons["conflicting_shipping_currency"]+=1
                continue
            shipping=_shipping_amount(raw_shipping)
            if shipping is None:
                rejection_reasons["invalid_or_missing_shipping"]+=1
                continue
            price=round(sold_price+shipping,2)
            price_basis="sold_price_plus_shipping"
            payload=dict(r)
            payload["price_basis"] = price_basis
            payload["normalized_sold_price"] = sold_price
            payload["normalized_shipping"] = shipping
            listing_format=_norm(r.get(cols["format"])) if cols["format"] else ""
            payload["normalized_listing_format"] = listing_format or None
            payload["normalized_quantity"] = quantity
            candidates.append(EvidenceRecord(
                provider=self.provider_name,record_type="sold",source_item_id=sid,
                title=title,price=price,event_date=sold_date,
                url=raw_url,currency=currency,payload=payload,
            ))

        grouped=defaultdict(list)
        for record in candidates:
            grouped[(record.source_item_id,record.event_date)].append(record)
        records=[]
        deduplicated_rows=0
        for group in grouped.values():
            fingerprints={(
                r.title,
                r.price,
                r.event_date,
                r.currency,
                r.payload.get("price_basis"),
                r.payload.get("normalized_sold_price"),
                r.payload.get("normalized_shipping"),
                r.payload.get("normalized_listing_format"),
                r.payload.get("normalized_quantity"),
            ) for r in group}
            if len(fingerprints)>1:
                rejection_reasons["conflicting_duplicate_evidence"]+=len(group)
                continue
            records.append(group[0])
            deduplicated_rows+=len(group)-1

        rejected_rows=sum(rejection_reasons.values())
        return ProviderResult(records,query,self.provider_name,{
            "path":str(p),"rows":len(rows),"columns":cols,
            "price_basis":"sold_price_plus_shipping",
            "accepted_rows":len(records),"deduplicated_rows":deduplicated_rows,"rejected_rows":rejected_rows,
            "rejection_reasons":dict(sorted(rejection_reasons.items())),
        })