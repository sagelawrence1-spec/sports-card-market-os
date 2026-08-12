import argparse, csv, sqlite3
from pathlib import Path
from providers import EbayBrowseProvider, EbayProductResearchProvider
from entity_matcher import SportsCardEntityMatcher, build_ebay_query
from evidence_store import EvidenceStore


def get_asset(db_path,card_id):
    conn=sqlite3.connect(db_path); conn.row_factory=sqlite3.Row
    row=conn.execute("SELECT * FROM assets WHERE card_id=?",(card_id,)).fetchone()
    if not row: raise KeyError(f"Unknown card_id {card_id}")
    return dict(row)


def ingest_records(records,asset,query,store):
    matcher=SportsCardEntityMatcher()
    accepted=review=rejected=0
    for rec in records:
        d=matcher.match(asset,rec.title)
        store.save(rec,asset["card_id"],query,d)
        if d.accepted: accepted+=1
        elif d.reason=="manual_review": review+=1
        else: rejected+=1
    return {"accepted":accepted,"review":review,"rejected":rejected,"total":len(records)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=["active","product-research"])
    p.add_argument("card_id")
    p.add_argument("--warehouse",default="market.sqlite")
    p.add_argument("--evidence",default="evidence.sqlite")
    p.add_argument("--file")
    p.add_argument("--limit",type=int,default=100)
    p.add_argument("--category-id")
    a=p.parse_args()
    asset=get_asset(a.warehouse,a.card_id)
    query=build_ebay_query(asset)
    if a.mode=="active":
        result=EbayBrowseProvider().search_active(query,limit=a.limit,category_id=a.category_id)
    else:
        if not a.file: p.error("--file is required for product-research mode")
        result=EbayProductResearchProvider().load_csv(a.file,query=query)
    stats=ingest_records(result.records,asset,query,EvidenceStore(a.evidence))
    print("query:",query)
    print("provider:",result.provider)
    print("stats:",stats)

if __name__=="__main__": main()
