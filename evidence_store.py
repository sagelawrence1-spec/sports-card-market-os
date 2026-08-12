import sqlite3, json, hashlib, uuid
from datetime import datetime

from entity_matcher import norm

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
  run_id TEXT,
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
CREATE TABLE IF NOT EXISTS identity_alias_adjudications(
  title_key TEXT NOT NULL,
  title TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  reviewer_id TEXT NOT NULL,
  approved INTEGER NOT NULL CHECK(approved IN (0,1)),
  evidence_id TEXT,
  adjudicated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(title_key,asset_id,reviewer_id)
);
CREATE INDEX IF NOT EXISTS idx_alias_adjudications_title ON identity_alias_adjudications(title_key);
CREATE TABLE IF NOT EXISTS market_runs(
  run_id TEXT PRIMARY KEY,
  as_of TEXT NOT NULL,
  source TEXT NOT NULL,
  status TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  started_at TEXT DEFAULT CURRENT_TIMESTAMP,
  completed_at TEXT
);
CREATE TABLE IF NOT EXISTS card_market_history(
  run_id TEXT NOT NULL,
  card_id TEXT NOT NULL,
  as_of TEXT NOT NULL,
  fair_value REAL,
  range_low REAL,
  range_high REAL,
  evidence_grade TEXT NOT NULL,
  confidence REAL NOT NULL,
  accepted_sales INTEGER NOT NULL,
  accepted_active INTEGER NOT NULL,
  review_count INTEGER NOT NULL,
  rejected_count INTEGER NOT NULL,
  lowest_ask REAL,
  median_ask REAL,
  state_json TEXT NOT NULL,
  PRIMARY KEY(run_id,card_id)
);
CREATE INDEX IF NOT EXISTS idx_market_history_card ON card_market_history(card_id,as_of);
CREATE TABLE IF NOT EXISTS recommendation_journal(
  run_id TEXT NOT NULL,
  card_id TEXT NOT NULL,
  action TEXT NOT NULL,
  fair_value REAL,
  confidence REAL,
  evidence_grade TEXT,
  thesis TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(run_id,card_id)
);
'''

class EvidenceStore:
    def __init__(self,path):
        self.conn=sqlite3.connect(str(path))
        self.conn.row_factory=sqlite3.Row
        self.conn.executescript(SCHEMA)
        columns={row["name"] for row in self.conn.execute("PRAGMA table_info(source_evidence)")}
        if "run_id" not in columns:
            self.conn.execute("ALTER TABLE source_evidence ADD COLUMN run_id TEXT")
        self.conn.commit()

    def save(self,record,card_id,query,decision,run_id=None):
        raw=json.dumps(record.payload,sort_keys=True,default=str)
        source_item_id=str(record.source_item_id or "").strip()
        source_platform=str((record.payload or {}).get("source_platform") or "").strip().lower()
        if source_platform=="ebay" and source_item_id.lower().startswith(("ebay:","ebay-")):
            source_item_id=source_item_id[5:]
        if (record.provider.startswith("ebay_") or source_platform=="ebay") and source_item_id and not source_item_id.startswith("row-"):
            base=f"ebay|{record.record_type}|{source_item_id}"
        else:
            base=f"{record.provider}|{record.record_type}|{source_item_id}|{record.event_date}|{record.title}|{record.price}"
        eid=hashlib.sha256(base.encode()).hexdigest()[:32]
        self.conn.execute('''INSERT OR REPLACE INTO source_evidence(
          evidence_id,provider,record_type,source_item_id,card_id,query,title,price,currency,event_date,url,
          match_score,match_status,match_reason,match_diagnostics_json,raw_payload_json,run_id)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
            eid,record.provider,record.record_type,record.source_item_id,card_id,query,record.title,record.price,
            record.currency,record.event_date,record.url,decision.score,
            "accepted" if decision.accepted else ("review" if decision.reason=="manual_review" else "rejected"),
            decision.reason,json.dumps(decision.diagnostics,sort_keys=True),raw,run_id
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

    def adjudicate(self,evidence_id,approved,reviewer_id=None):
        row=self.conn.execute(
            "SELECT evidence_id,title,card_id FROM source_evidence WHERE evidence_id=? AND match_status='review'",
            (evidence_id,)
        ).fetchone()
        if row is None:
            return False
        if reviewer_id is not None and not str(reviewer_id).strip():
            raise ValueError("reviewer_id cannot be blank")

        status="accepted" if approved else "rejected"
        reason="manual_override" if approved else "manual_reject"
        cur=self.conn.execute(
            "UPDATE source_evidence SET match_status=?,match_reason=? WHERE evidence_id=? AND match_status='review'",
            (status,reason,evidence_id)
        )
        if cur.rowcount == 1 and reviewer_id is not None:
            title=str(row["title"] or "").strip()
            asset_id=str(row["card_id"] or "").strip()
            title_key=norm(title)
            if not title_key or not asset_id:
                self.conn.rollback()
                raise ValueError("review evidence must have title and card_id to learn an alias")
            self.conn.execute('''INSERT INTO identity_alias_adjudications(
              title_key,title,asset_id,reviewer_id,approved,evidence_id,adjudicated_at)
              VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)
              ON CONFLICT(title_key,asset_id,reviewer_id) DO UPDATE SET
                title=excluded.title, approved=excluded.approved, evidence_id=excluded.evidence_id,
                adjudicated_at=CURRENT_TIMESTAMP''',(
                title_key,title,asset_id,str(reviewer_id).strip(),1 if approved else 0,evidence_id
            ))
        self.conn.commit()
        return cur.rowcount == 1

    def alias_diagnostics(self,title,min_approvals=2):
        if min_approvals < 2:
            raise ValueError("min_approvals must be at least 2")
        title_key=norm(title)
        rows=self.conn.execute('''SELECT asset_id,reviewer_id,approved
          FROM identity_alias_adjudications WHERE title_key=?''',(title_key,)).fetchall()
        if not rows:
            return {"known":False,"active":False,"conflicting":False}

        approvals={}
        rejections={}
        for row in rows:
            target=approvals if row["approved"] else rejections
            target.setdefault(row["asset_id"],set()).add(row["reviewer_id"])

        approved_assets=[asset_id for asset_id,reviewers in approvals.items() if reviewers]
        conflicting=len(approved_assets)>1
        qualified=[
            asset_id for asset_id,reviewers in approvals.items()
            if len(reviewers)>=min_approvals and not rejections.get(asset_id)
        ]
        resolved=qualified[0] if len(qualified)==1 and not conflicting else None
        return {
            "known":True,
            "active":resolved is not None,
            "resolved_asset_id":resolved,
            "conflicting":conflicting,
            "approval_counts":{asset_id:len(reviewers) for asset_id,reviewers in approvals.items()},
            "rejection_counts":{asset_id:len(reviewers) for asset_id,reviewers in rejections.items()},
        }

    def resolved_alias_asset_id(self,title,min_approvals=2):
        return self.alias_diagnostics(title,min_approvals=min_approvals).get("resolved_asset_id")

    def accepted_sales(self,card_id):
        return self.conn.execute('''SELECT * FROM source_evidence WHERE card_id=? AND record_type='sold' AND match_status='accepted' ORDER BY event_date DESC''',(card_id,)).fetchall()

    def evidence_counts(self,card_id,run_id=None):
        q="SELECT match_status,COUNT(*) FROM source_evidence WHERE card_id=?"
        args=[card_id]
        if run_id:
            q+=" AND run_id=?"; args.append(run_id)
        q+=" GROUP BY match_status"
        return dict(self.conn.execute(q,args).fetchall())

    def start_market_run(self,as_of,source,metadata=None):
        run_id=uuid.uuid4().hex
        self.conn.execute('''INSERT INTO market_runs(run_id,as_of,source,status,metadata_json)
          VALUES(?,?,?,?,?)''',(run_id,as_of,source,"running",json.dumps(metadata or {},sort_keys=True)))
        self.conn.commit(); return run_id

    def finish_market_run(self,run_id,status,metadata=None):
        self.conn.execute('''UPDATE market_runs SET status=?,metadata_json=?,completed_at=? WHERE run_id=?''',(
            status,json.dumps(metadata or {},sort_keys=True),datetime.utcnow().isoformat()+"Z",run_id
        ))
        self.conn.commit()

    def save_market_state(self,run_id,state):
        evidence_range=state.get("evidence_range") or {}
        self.conn.execute('''INSERT OR REPLACE INTO card_market_history(
          run_id,card_id,as_of,fair_value,range_low,range_high,evidence_grade,confidence,
          accepted_sales,accepted_active,review_count,rejected_count,lowest_ask,median_ask,state_json)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
            run_id,state["card_id"],state["last_updated"],state.get("fair_value"),
            evidence_range.get("low"),evidence_range.get("high"),state["evidence_grade"],state["confidence"],
            state.get("accepted_sales_30d",0),state.get("accepted_active_count",0),state.get("review_count",0),
            state.get("excluded_count",0),state.get("lowest_ask"),state.get("median_ask"),
            json.dumps(state,sort_keys=True)
        ))
        if state.get("action"):
            self.conn.execute('''INSERT OR IGNORE INTO recommendation_journal(
              run_id,card_id,action,fair_value,confidence,evidence_grade,thesis)
              VALUES(?,?,?,?,?,?,?)''',(
                run_id,state["card_id"],state["action"],state.get("fair_value"),state["confidence"],
                state["evidence_grade"],state.get("thesis")
            ))
        self.conn.commit()

    def previous_market_state(self,card_id):
        row=self.conn.execute('''SELECT state_json FROM card_market_history WHERE card_id=?
          ORDER BY as_of DESC,rowid DESC LIMIT 1''',(card_id,)).fetchone()
        return json.loads(row["state_json"]) if row else None

    def market_history(self,card_id):
        return [json.loads(row["state_json"]) for row in self.conn.execute(
            "SELECT state_json FROM card_market_history WHERE card_id=? ORDER BY as_of, rowid",(card_id,)
        )]

    def counts(self):
        return dict(self.conn.execute("SELECT match_status,COUNT(*) FROM source_evidence GROUP BY match_status").fetchall())
