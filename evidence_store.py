import sqlite3, json, hashlib
from datetime import datetime

SCHEMA=r'''
CREATE TABLE IF NOT EXISTS source_evidence(
  evidence_id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  record_type TEXT NOT NULL,
  source_item_id TEXT,
  card_id TEXT,
  query TEXT,
  title TEXT,
  price REAL,
  currency TEXT,
  event_date TEXT,
  url TEXT,
  match_score REAL,
  match_status TEXT,
  match_reason TEXT,
  match_diagnostics_json TEXT,
  raw_payload_json TEXT,
  ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_evidence_card ON source_evidence(card_id,record_type,event_date);
CREATE INDEX IF NOT EXISTS idx_evidence_provider_item ON source_evidence(provider,source_item_id);
CREATE TABLE IF NOT EXISTS import_batches(
  batch_id TEXT PRIMARY KEY, source_sha256 TEXT UNIQUE NOT NULL, provider TEXT NOT NULL,
  source_name TEXT, accepted_count INTEGER NOT NULL, review_count INTEGER NOT NULL,
  rejected_count INTEGER NOT NULL, affected_cards_json TEXT NOT NULL,
  imported_at TEXT DEFAULT CURRENT_TIMESTAMP
);
'''

class EvidenceStore:
    def __init__(self,path):
        self.conn=sqlite3.connect(str(path))
        self.conn.executescript(SCHEMA); self.conn.commit()

    def save(self,record,card_id,query,decision):
        raw=json.dumps(record.payload,sort_keys=True,default=str)
        base=f"{record.provider}|{record.record_type}|{record.source_item_id}|{record.event_date}|{record.price}"
        eid=hashlib.sha256(base.encode()).hexdigest()[:32]
        self.conn.execute('''INSERT OR REPLACE INTO source_evidence(
          evidence_id,provider,record_type,source_item_id,card_id,query,title,price,currency,event_date,url,
          match_score,match_status,match_reason,match_diagnostics_json,raw_payload_json)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
            eid,record.provider,record.record_type,record.source_item_id,card_id,query,record.title,record.price,
            record.currency,record.event_date,record.url,decision.score,
            "accepted" if decision.accepted else ("review" if decision.reason=="manual_review" else "rejected"),
            decision.reason,json.dumps(decision.diagnostics,sort_keys=True),raw
        ))
        self.conn.commit(); return eid

    def record_batch(self, source_bytes, provider, source_name, counts, affected_cards):
        fingerprint=hashlib.sha256(source_bytes).hexdigest()
        batch_id=fingerprint[:32]
        try:
            self.conn.execute('''INSERT INTO import_batches(batch_id,source_sha256,provider,source_name,
              accepted_count,review_count,rejected_count,affected_cards_json) VALUES(?,?,?,?,?,?,?,?)''',(
              batch_id,fingerprint,provider,source_name,int(counts.get("accepted",0)),
              int(counts.get("review",0)),int(counts.get("rejected",0)),
              json.dumps(sorted(set(affected_cards)))
            ))
            self.conn.commit()
            return {"batch_id":batch_id,"duplicate":False}
        except sqlite3.IntegrityError:
            return {"batch_id":batch_id,"duplicate":True}

    def review_queue(self, status="review"):
        return self.conn.execute("SELECT * FROM source_evidence WHERE match_status=? ORDER BY ingested_at",(status,)).fetchall()

    def adjudicate(self,evidence_id,approved):
        status="accepted" if approved else "rejected"
        reason="manual_override" if approved else "manual_reject"
        cur=self.conn.execute("UPDATE source_evidence SET match_status=?,match_reason=? WHERE evidence_id=? AND match_status='review'",(status,reason,evidence_id))
        self.conn.commit()
        return cur.rowcount == 1

    def accepted_sales(self,card_id):
        return self.conn.execute('''SELECT * FROM source_evidence WHERE card_id=? AND record_type='sold' AND match_status='accepted' ORDER BY event_date DESC''',(card_id,)).fetchall()

    def counts(self):
        return dict(self.conn.execute("SELECT match_status,COUNT(*) FROM source_evidence GROUP BY match_status").fetchall())
