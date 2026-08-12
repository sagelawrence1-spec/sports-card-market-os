"use client";

import { useMemo, useState } from "react";
import marketScan from "../public/data/market-scan.json";

type View = "scan" | "opportunities" | "card" | "player" | "portfolio" | "research";
type EvidenceRange = { low: number; high: number } | null;
type MarketItem = {
  observation_id: string;
  card_id: string;
  sport: string;
  player: string;
  card: string;
  action: string | null;
  engine_classification: string;
  alerts: string[];
  confidence: number;
  evidence_grade: string;
  fair_value: number | null;
  evidence_range?: EvidenceRange;
  move_30d: number | null;
  liquidity_score: number;
  accepted_sales_30d: number;
  accepted_sales_total?: number;
  accepted_active_count?: number;
  review_count?: number;
  excluded_count?: number;
  lowest_ask?: number | null;
  median_ask?: number | null;
  latest_sale_date?: string | null;
  last_updated?: string;
  ideal_entry?: number | null;
  do_not_chase?: number | null;
  thesis: string;
  evidence_explanation?: string;
  blockers?: string[];
};
type MarketPayload = {
  generated_at: string;
  source: {
    kind: "illustrative_alpha" | "scheduled_evidence" | "blocked_evidence" | string;
    label: string;
    provenance?: { sold_source_available?: boolean; listing_source_available?: boolean };
  };
  universe_size: number;
  items: MarketItem[];
};

const marketData = marketScan as unknown as MarketPayload;
const nav: [View, string][] = [
  ["scan", "Market Scan"],
  ["opportunities", "Opportunities"],
  ["card", "Card Intelligence"],
  ["player", "Player Market"],
  ["portfolio", "Portfolio"],
  ["research", "Research"],
];
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const scanTime = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
  timeZone: "America/Phoenix",
  timeZoneName: "short",
}).format(new Date(marketData.generated_at));

const sourceBadge = marketData.source.kind === "illustrative_alpha"
  ? "ILLUSTRATIVE ALPHA DATA"
  : marketData.source.kind === "scheduled_evidence"
    ? "LIVE EVIDENCE"
    : "SOLD DATA ACCESS BLOCKED";

const formatPrice = (value?: number | null) => value == null ? "—" : money.format(value);
const formatMove = (value: number | null) => value == null ? "—" : `${value >= 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
const formatDate = (value?: string | null) => value ? new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(new Date(`${value.slice(0, 10)}T12:00:00Z`)) : "—";

const signals = marketData.items.map((item) => ({
  raw: item,
  signal: item.action ?? "MONITOR",
  tag: item.alerts[0] ?? (item.engine_classification === "EVIDENCE_READY" ? "EVIDENCE READY" : "EVIDENCE GATED"),
  sport: item.sport,
  card: item.card,
  price: item.fair_value == null ? "Not enough evidence" : money.format(item.fair_value),
  move: formatMove(item.move_30d),
  evidence: item.evidence_grade,
  confidence: item.confidence,
  why: item.thesis,
  actionable: Boolean(item.action),
}));

export default function Home() {
  const [view, setView] = useState<View>("scan");
  const [sport, setSport] = useState("All sports");
  const [signalFilter, setSignalFilter] = useState("All signals");
  const [selectedCardId, setSelectedCardId] = useState(marketData.items[0]?.card_id ?? "");
  const selected = marketData.items.find((item) => item.card_id === selectedCardId) ?? marketData.items[0];
  const actionable = signals.filter((signal) => signal.actionable);
  const valuedCount = marketData.items.filter((item) => item.fair_value != null && ["A", "B"].includes(item.evidence_grade)).length;
  const visibleSignals = useMemo(() => signals.filter((signal) => (
    (sport === "All sports" || signal.sport === sport)
    && (signalFilter === "All signals" || signal.signal === signalFilter)
  )), [sport, signalFilter]);

  const openCard = (cardId: string) => {
    setSelectedCardId(cardId);
    setView("card");
  };

  return <div className="shell">
    <aside>
      <div className="logo"><span>OS</span><div><b>Market OS</b><small>SPORTS CARD INTELLIGENCE</small></div></div>
      <div className="nav-label">COMMAND CENTER</div>
      {nav.map(([id, label]) => <button key={id} onClick={() => setView(id)} className={view === id ? "active" : ""}><i>{id === "scan" ? "⌁" : id === "opportunities" ? "⚡" : id === "card" ? "▣" : id === "player" ? "◎" : id === "portfolio" ? "◫" : "≡"}</i>{label}</button>)}
      <div className="system"><span className={marketData.source.kind === "blocked_evidence" ? "blocked" : ""}></span><div><b>{marketData.source.kind === "blocked_evidence" ? "EVIDENCE BLOCKED" : "MARKET ONLINE"}</b><small>{marketData.source.label}</small></div></div>
    </aside>
    <main>
      <header>
        <div className="search">⌕ <input aria-label="Search cards or players" placeholder="Search any card, player, set…" /></div>
        <div className={`data-state ${marketData.source.kind}`} title={marketData.source.label}>{sourceBadge}</div>
        <button className="scan-btn" onClick={() => setView("scan")}>View market scan</button><div className="avatar">SL</div>
      </header>

      {view === "scan" && <>
        <div className="page-head"><div><span className="kicker">MARKET COMMAND CENTER</span><h1>Market Scan</h1><p>Material changes across the monitored universe. Noise removed.</p></div><div className="asof">AS OF {scanTime.toUpperCase()}<br /><b>{marketData.universe_size} cards monitored</b></div></div>
        <div className="tape">
          <div><span>MARKET PULSE</span><b>{marketData.source.kind === "blocked_evidence" ? "Sold evidence blocked" : actionable.length ? "Selective strength" : "Evidence building"}</b></div>
          <div><span>ACTIONS CLEARING GATES</span><b className={actionable.length ? "green" : ""}>{actionable.length} actionable</b></div>
          <div><span>EVIDENCE HEALTH</span><b>{valuedCount} / {marketData.items.length} valued</b></div>
          <div><span>CAPITAL POSTURE</span><b>{actionable.length ? "Selective" : "Calibration gated"}</b></div>
        </div>
        <div className="toolbar"><div>{["All signals", "BUY", "ACCUMULATE", "HOLD", "TRIM", "SELL", "MONITOR"].map((filter) => <button onClick={() => setSignalFilter(filter)} className={signalFilter === filter ? "on" : ""} key={filter}>{filter}</button>)}</div><select value={sport} onChange={(event) => setSport(event.target.value)}><option>All sports</option><option>NBA</option><option>MLB</option><option>NFL</option></select></div>
        <section className="signal-table"><div className="table-title"><b>Highest-conviction changes</b><span>Ranked by signal strength × evidence quality</span></div><div className="thead"><span>SIGNAL</span><span>ASSET</span><span>FAIR VALUE</span><span>30D</span><span>EVIDENCE</span><span>CONF.</span></div>{visibleSignals.map((signal) => <button className="row" key={signal.raw.card_id} onClick={() => openCard(signal.raw.card_id)}><span><b className={`pill ${signal.signal.toLowerCase()}`}>{signal.signal}</b><small>{signal.tag}</small></span><span><b>{signal.card}</b><small>{signal.sport} · {signal.raw.accepted_sales_total ?? 0} accepted sales</small></span><b>{signal.price}</b><b className={signal.move.startsWith("+") ? "green" : signal.move === "—" ? "muted" : "red"}>{signal.move}</b><b className="evidence">{signal.evidence}</b><b>{signal.confidence}%</b></button>)}</section>
      </>}

      {view === "opportunities" && <>
        <div className="page-head"><div><span className="kicker">PROACTIVE DISCOVERY</span><h1>Opportunity Feed</h1><p>Only opportunities that clear evidence and calibration gates.</p></div></div>
        {actionable.length ? <div className="op-grid">{actionable.slice(0, 3).map((signal, index) => <article className="op" key={signal.raw.card_id}><div className="op-top"><b>{signal.tag} · {signal.sport}</b><span>{signal.confidence}% confidence</span></div><h2>{index === 0 ? "Potential grail compression" : index === 1 ? "Premium rookie dislocation" : "Supply expansion warning"}</h2><h3>{signal.card}</h3><div className="drivers"><span><small>ACCEPTED SALES</small><b>{signal.raw.accepted_sales_total ?? 0}</b></span><span><small>ACTIVE LISTINGS</small><b>{signal.raw.accepted_active_count ?? 0}</b></span><span><small>EVIDENCE</small><b>{signal.evidence}</b></span></div><p>{signal.why}</p><div className="action"><span>ACTION</span><b>{signal.signal}{signal.raw.ideal_entry ? ` below ${formatPrice(signal.raw.ideal_entry)}` : ""}</b></div></article>)}</div> : <div className="evidence-empty"><span>EVIDENCE GATE ACTIVE</span><h2>No opportunity clears the evidence and calibration gates.</h2><p>The system is monitoring the market and will not manufacture an action from weak or unavailable evidence.</p></div>}
      </>}

      {view === "card" && selected && <>
        <div className="crumb">Market Scan / {selected.sport} / {selected.player}</div>
        <div className="card-hero"><div><span className="kicker">CARD INTELLIGENCE</span><h1>{selected.card}</h1><p>{selected.card_id}</p></div><div><b className={`pill ${(selected.action ?? "monitor").toLowerCase()}`}>{selected.action ?? "EVIDENCE GATED"}</b><small>{selected.confidence}% confidence · Evidence {selected.evidence_grade}</small></div></div>
        <div className="metric-groups">
          <div><span><small>Fair value</small><b>{selected.fair_value == null ? "Not enough evidence" : formatPrice(selected.fair_value)}</b></span><span><small>30 days</small><b className={(selected.move_30d ?? 0) > 0 ? "green" : ""}>{formatMove(selected.move_30d)}</b></span><span><small>Evidence range</small><b>{selected.evidence_range ? `${formatPrice(selected.evidence_range.low)}–${formatPrice(selected.evidence_range.high)}` : "—"}</b></span></div>
          <div><span><small>Accepted sales</small><b>{selected.accepted_sales_total ?? 0}</b></span><span><small>Liquidity</small><b>{selected.liquidity_score} / 100</b></span><span><small>Evidence</small><b>{selected.evidence_grade}</b></span></div>
          <div><span><small>Active listings</small><b>{selected.accepted_active_count ?? 0}</b></span><span><small>Needs review</small><b>{selected.review_count ?? 0}</b></span><span><small>Latest sale</small><b>{formatDate(selected.latest_sale_date)}</b></span></div>
        </div>
        <div className="levels"><div><small>IDEAL ENTRY</small><b>{formatPrice(selected.ideal_entry)}</b></div><div><small>DO NOT CHASE</small><b>{formatPrice(selected.do_not_chase)}</b></div><div><small>LOWEST / MEDIAN ASK</small><b>{formatPrice(selected.lowest_ask)} / {formatPrice(selected.median_ask)}</b></div></div>
        <section className="thesis"><div><h2>Why this evidence should—or should not—be trusted</h2><p>{selected.thesis}</p><h3>Evidence state</h3><p>{selected.evidence_explanation ?? "No evidence explanation is available."}</p>{selected.blockers?.length ? <div className="blockers"><strong>Before capital can move</strong>{selected.blockers.map((blocker) => <span key={blocker}>{blocker}</span>)}</div> : null}</div><aside><span>{selected.accepted_sales_total ?? 0} accepted sales</span><span>{selected.excluded_count ?? 0} excluded comps</span><span>{selected.review_count ?? 0} awaiting review</span><span>Updated {formatDate(selected.last_updated)}</span></aside></section>
      </>}

      {view === "player" && <><div className="page-head"><div><span className="kicker">PLAYER MARKET</span><h1>Stephen Curry</h1><p>Where value, liquidity, and hierarchy are moving across the player market.</p></div></div><div className="player-summary"><div><small>PLAYER MARKET VALUE</small><b>+12.8%</b><span>90 days</span></div><div><small>STRONGEST SEGMENT</small><b>Premium rookies</b><span>velocity +27%</span></div><div><small>CURRENT MISPRICING</small><b>Topps Chrome PSA 9</b><span>grail compression</span></div></div><section className="hierarchy"><h2>Rookie hierarchy</h2>{["National Treasures RPA /99", "Topps Chrome Refractor", "Topps Chrome Base", "Panini Prestige #157"].map((name, index) => <div key={name}><b>#{index + 1}</b><span><strong>{name}</strong><small>{index === 0 ? "Long-term grail" : index === 1 ? "Best $10k expression" : index === 2 ? "Best $5k expression" : "Best $500 expression"}</small></span><span className={index === 2 ? "green" : ""}>{index === 2 ? "ACCUMULATE" : "HOLD"}</span><strong>{["$184k", "$32.4k", "$4.82k", "$640"][index]}</strong></div>)}</section></>}
      {view === "portfolio" && <><div className="page-head"><div><span className="kicker">CAPITAL ALLOCATOR</span><h1>Deploy $5,000</h1><p>Best risk-adjusted action across fresh capital and current holdings.</p></div></div><div className="allocation"><article><span className="rank">01</span><div><b>Buy Curry Topps Chrome PSA 9</b><p>Maximum entry $4,650 · 6–18 month hold</p></div><strong>70% · $3,500</strong></article><article><span className="rank">02</span><div><b>Keep cash available</b><p>Wait for evidence-confirmed dislocations</p></div><strong>30% · $1,500</strong></article><div className="no-action"><b>No forced deployment</b><p>The allocator preserves cash when no opportunity clears its evidence and return hurdles.</p></div></div></>}
      {view === "research" && <><div className="page-head"><div><span className="kicker">MARKET INTELLIGENCE</span><h1>Research Desk</h1><p>Why markets moved, what could happen next, and which cards express it best.</p></div></div><div className="research-grid">{[["ATHLETE CATALYST", "Curry extension and title-window repricing", "Collector demand is rotating toward premium rookies as long-term career certainty increases."], ["MARKET STRUCTURE", "Grail compression is widening", "Superior Curry tiers moved 2.2× faster than liquid substitutes over 90 days."], ["SUPPLY WATCH", "Modern PSA 10 population pressure", "Select 2020–23 silver parallels show supply growth outpacing buyer absorption."], ["AUCTION BEHAVIOR", "High-end bidding depth improves", "Three consecutive premium lots cleared above estimate with broader bidder participation."]].map(([tag, title, body]) => <article key={title}><span>{tag}</span><h2>{title}</h2><p>{body}</p><button>Open research note →</button></article>)}</div></>}
    </main>
  </div>;
}
