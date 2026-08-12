import sqlite3, csv, json
from pathlib import Path

SCHEMA = r'''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS assets(
  card_id TEXT PRIMARY KEY,
  observation_id TEXT,
  sport TEXT, league TEXT, player TEXT, player_archetype TEXT,
  year INTEGER, manufacturer TEXT, set_name TEXT, card_number TEXT,
  rookie_flag INTEGER, parallel TEXT, serial_number INTEGER,
  autograph INTEGER, grade_company TEXT, grade REAL,
  card_tier TEXT, tier_rank INTEGER,
  source TEXT, ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sales(
  sale_id TEXT PRIMARY KEY,
  card_id TEXT NOT NULL,
  sale_date TEXT NOT NULL,
  sale_price REAL NOT NULL,
  platform TEXT, sale_type TEXT, buyer_id_hash TEXT,
  source TEXT, ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sales_card_date ON sales(card_id,sale_date);
CREATE TABLE IF NOT EXISTS market_snapshots(
  card_id TEXT NOT NULL,
  snapshot_date TEXT NOT NULL,
  active_listings INTEGER,
  lowest_ask REAL,
  median_ask REAL,
  source TEXT,
  ingested_at TEXT DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(card_id,snapshot_date,source)
);
CREATE TABLE IF NOT EXISTS population_snapshots(
  card_id TEXT NOT NULL,
  snapshot_date TEXT NOT NULL,
  grade_company TEXT,
  grade REAL,
  population INTEGER,
  source TEXT,
  ingested_at TEXT DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(card_id,snapshot_date,grade_company,grade,source)
);
CREATE TABLE IF NOT EXISTS athlete_snapshots(
  player TEXT NOT NULL,
  sport TEXT,
  snapshot_date TEXT NOT NULL,
  age REAL,
  performance_percentile REAL,
  season_trend_percentile REAL,
  collector_search_index REAL,
  media_attention_index REAL,
  social_momentum_index REAL,
  role_change_flag INTEGER,
  temporary_supply_shock_flag INTEGER,
  no_near_term_catalyst_flag INTEGER,
  event_probability_index REAL,
  injury_risk_index REAL,
  source TEXT,
  ingested_at TEXT DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(player,snapshot_date,source)
);
CREATE TABLE IF NOT EXISTS hierarchy_comparables(
  card_id TEXT PRIMARY KEY,
  accepted_grail_substitute_flag INTEGER,
  superior_tier_market_value_current REAL,
  superior_tier_market_value_90d REAL,
  peer_cohort_index_value_current REAL,
  peer_cohort_index_value_90d REAL,
  estimated_print_run INTEGER,
  source TEXT,
  ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS scan_runs(
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  scanned_at TEXT DEFAULT CURRENT_TIMESTAMP,
  source TEXT
);
CREATE TABLE IF NOT EXISTS scan_signals(
  run_id INTEGER NOT NULL,
  card_id TEXT NOT NULL,
  signal TEXT,
  confidence REAL,
  ir REAL, rar REAL, mi REAL, cie REAL,
  alerts TEXT,
  thesis TEXT,
  diagnostics_json TEXT,
  PRIMARY KEY(run_id,card_id)
);
'''

class Warehouse:
    def __init__(self, path):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def upsert_assets(self, rows, source="unknown"):
        q='''INSERT INTO assets(card_id,observation_id,sport,league,player,player_archetype,year,manufacturer,set_name,card_number,rookie_flag,parallel,serial_number,autograph,grade_company,grade,card_tier,tier_rank,source)
             VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
             ON CONFLICT(card_id) DO UPDATE SET observation_id=excluded.observation_id,sport=excluded.sport,league=excluded.league,player=excluded.player,player_archetype=excluded.player_archetype,year=excluded.year,manufacturer=excluded.manufacturer,set_name=excluded.set_name,card_number=excluded.card_number,rookie_flag=excluded.rookie_flag,parallel=excluded.parallel,serial_number=excluded.serial_number,autograph=excluded.autograph,grade_company=excluded.grade_company,grade=excluded.grade,card_tier=excluded.card_tier,tier_rank=excluded.tier_rank,source=excluded.source'''
        vals=[]
        for r in rows:
            vals.append((r.get('card_id'),r.get('observation_id'),r.get('sport'),r.get('league'),r.get('player'),r.get('player_archetype'),r.get('year') or None,r.get('manufacturer'),r.get('set'),r.get('card_number'),r.get('rookie_flag') or 0,r.get('parallel'),r.get('serial_number') or None,r.get('autograph') or 0,r.get('grade_company'),r.get('grade') or None,r.get('card_tier'),r.get('tier_rank') or None,source))
        self.conn.executemany(q,vals); self.conn.commit()

    def insert_sales(self, rows, source="unknown"):
        q='''INSERT OR IGNORE INTO sales(sale_id,card_id,sale_date,sale_price,platform,sale_type,buyer_id_hash,source) VALUES(?,?,?,?,?,?,?,?)'''
        vals=[(r.get('sale_id'),r.get('card_id'),r.get('sale_date'),r.get('sale_price'),r.get('platform'),r.get('sale_type'),r.get('buyer_id_hash'),source) for r in rows]
        self.conn.executemany(q,vals); self.conn.commit()

    def insert_market(self, rows, source="unknown"):
        q='''INSERT OR REPLACE INTO market_snapshots(card_id,snapshot_date,active_listings,lowest_ask,median_ask,source) VALUES(?,?,?,?,?,?)'''
        vals=[(r.get('card_id'),r.get('snapshot_date'),r.get('active_listings'),r.get('lowest_ask'),r.get('median_ask'),source) for r in rows]
        self.conn.executemany(q,vals); self.conn.commit()

    def insert_pops(self, rows, source="unknown"):
        q='''INSERT OR REPLACE INTO population_snapshots(card_id,snapshot_date,grade_company,grade,population,source) VALUES(?,?,?,?,?,?)'''
        vals=[(r.get('card_id'),r.get('snapshot_date'),r.get('grade_company'),r.get('grade'),r.get('population'),source) for r in rows]
        self.conn.executemany(q,vals); self.conn.commit()

    def insert_athletes(self, rows, source="unknown"):
        q='''INSERT OR REPLACE INTO athlete_snapshots(player,sport,snapshot_date,age,performance_percentile,season_trend_percentile,collector_search_index,media_attention_index,social_momentum_index,role_change_flag,temporary_supply_shock_flag,no_near_term_catalyst_flag,event_probability_index,injury_risk_index,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''
        vals=[(r.get('player'),r.get('sport'),r.get('snapshot_date'),r.get('age'),r.get('performance_percentile'),r.get('season_trend_percentile'),r.get('collector_search_index'),r.get('media_attention_index'),r.get('social_momentum_index'),r.get('role_change_flag'),r.get('temporary_supply_shock_flag'),r.get('no_near_term_catalyst_flag'),r.get('event_probability_index'),r.get('injury_risk_index'),source) for r in rows]
        self.conn.executemany(q,vals); self.conn.commit()

    def insert_hierarchy(self, rows, source="unknown"):
        q='''INSERT OR REPLACE INTO hierarchy_comparables(card_id,accepted_grail_substitute_flag,superior_tier_market_value_current,superior_tier_market_value_90d,peer_cohort_index_value_current,peer_cohort_index_value_90d,estimated_print_run,source) VALUES(?,?,?,?,?,?,?,?)'''
        vals=[(r.get('card_id'),r.get('accepted_grail_substitute_flag'),r.get('superior_tier_market_value_current'),r.get('superior_tier_market_value_90d'),r.get('peer_cohort_index_value_current'),r.get('peer_cohort_index_value_90d'),r.get('estimated_print_run') or None,source) for r in rows]
        self.conn.executemany(q,vals); self.conn.commit()

    def counts(self):
        tables=['assets','sales','market_snapshots','population_snapshots','athlete_snapshots','hierarchy_comparables','scan_runs','scan_signals']
        return {t:self.conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in tables}
