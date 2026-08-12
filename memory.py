import sqlite3, json
from pathlib import Path
from datetime import datetime

SCHEMA="""
CREATE TABLE IF NOT EXISTS scan_runs(
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  scanned_at TEXT NOT NULL,
  source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS signals(
  run_id INTEGER NOT NULL,
  card_id TEXT NOT NULL,
  signal TEXT NOT NULL,
  confidence REAL,
  ir REAL, rar REAL, mi REAL, cie REAL,
  alerts TEXT,
  diagnostics_json TEXT,
  PRIMARY KEY(run_id,card_id)
);
"""

class ScanMemory:
    def __init__(self,path):
        self.path=str(path)
        self.conn=sqlite3.connect(self.path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def save(self,source,signals):
        cur=self.conn.cursor()
        cur.execute("INSERT INTO scan_runs(scanned_at,source) VALUES(?,?)",(datetime.utcnow().isoformat(),str(source)))
        run_id=cur.lastrowid
        for s in signals:
            cur.execute(
                "INSERT INTO signals VALUES(?,?,?,?,?,?,?,?,?,?)",
                (run_id,s.card_id,s.signal,s.confidence,s.ir_score,s.rar_score,s.mi_score,s.cie_score,
                 "|".join(s.alerts),json.dumps(s.diagnostics,sort_keys=True))
            )
        self.conn.commit()
        return run_id

    def previous(self,card_id,before_run_id=None):
        q="""SELECT s.run_id,s.signal,s.confidence,s.ir,s.rar,s.mi,s.cie,s.alerts,s.diagnostics_json
             FROM signals s WHERE s.card_id=? """
        args=[card_id]
        if before_run_id is not None:
            q += "AND s.run_id < ? "
            args.append(before_run_id)
        q += "ORDER BY s.run_id DESC LIMIT 1"
        row=self.conn.execute(q,args).fetchone()
        return row
