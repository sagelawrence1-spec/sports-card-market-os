from pathlib import Path
from entity_matcher import SportsCardEntityMatcher
from evidence_store import EvidenceStore
from providers.ebay_product_research import EbayProductResearchProvider

def ingest_product_research(path, assets, evidence_path, dry_run=True):
    path=Path(path); source=path.read_bytes(); store=EvidenceStore(evidence_path)
    records=EbayProductResearchProvider().load_csv(str(path)).records
    matcher=SportsCardEntityMatcher(); routed=[]; counts={"accepted":0,"review":0,"rejected":0}
    for record in records:
        ranked=sorted(((matcher.match(asset,record.title),asset) for asset in assets),key=lambda x:x[0].score,reverse=True)
        decision,asset=ranked[0]
        if len(ranked)>1 and decision.accepted and ranked[1][0].score >= decision.score-3:
            decision=type(decision)(False,decision.score,"manual_review",{**decision.diagnostics,"ambiguous_candidates":[asset["card_id"],ranked[1][1]["card_id"]]})
        status="accepted" if decision.accepted else "review" if decision.reason=="manual_review" else "rejected"
        counts[status]+=1; routed.append((record,asset,decision,status))
    if dry_run:
        return {**counts,"batch_id":None,"duplicate":False,"written":0}
    fingerprint=store.record_batch(source,"ebay_product_research",path.name,counts,[x[1]["card_id"] for x in routed])
    if fingerprint["duplicate"]:
        return {**counts,**fingerprint,"written":0}
    for record,asset,decision,_ in routed: store.save(record,asset["card_id"],"bulk_import",decision)
    return {**counts,**fingerprint,"written":len(routed)}
