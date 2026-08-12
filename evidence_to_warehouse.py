import sqlite3, statistics, hashlib
from datetime import date, datetime
from dateutil import parser as dtparser
from warehouse import Warehouse


def iso_date(v):
    if not v: return date.today().isoformat()
    try: return dtparser.parse(str(v)).date().isoformat()
    except Exception: return str(v)[:10]


def materialize(evidence_db, warehouse_db, card_id, snapshot_date=None):
    edb=sqlite3.connect(evidence_db); edb.row_factory=sqlite3.Row
    wh=Warehouse(warehouse_db)
    accepted=edb.execute("SELECT * FROM source_evidence WHERE card_id=? AND match_status='accepted'",(card_id,)).fetchall()
    sold=[r for r in accepted if r['record_type']=='sold']
    active=[r for r in accepted if r['record_type']=='active_listing']

    sale_rows=[]
    for r in sold:
        sid=f"{r['provider']}:{r['source_item_id']}:{iso_date(r['event_date'])}:{r['price']}"
        sale_rows.append({
            'sale_id':hashlib.sha256(sid.encode()).hexdigest()[:32],
            'card_id':card_id,'sale_date':iso_date(r['event_date']),'sale_price':r['price'],
            'platform':'eBay','sale_type':None,'buyer_id_hash':None,
        })
    if sale_rows:
        wh.insert_sales(sale_rows,source='ebay_matched_evidence')

    market_rows=[]
    if active:
        prices=[float(r['price']) for r in active if r['price'] is not None]
        if prices:
            market_rows.append({
                'card_id':card_id,
                'snapshot_date':snapshot_date or date.today().isoformat(),
                'active_listings':len(prices),
                'lowest_ask':min(prices),
                'median_ask':statistics.median(prices),
            })
            wh.insert_market(market_rows,source='ebay_browse_matched')
    return {'accepted_sold_materialized':len(sale_rows),'accepted_active_materialized':len(active),'market_snapshot_written':bool(market_rows)}
