"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import marketScan from "../public/data/market-scan.json";
import {
  buildRouteSearch,
  buildReviewQueue,
  deriveMarketState,
  filterMarketItems,
  getSelectedCard,
  isActionable,
  parseRoute,
  plainBlocker,
  rankPriority,
  safeAction,
  valuationTrustGates,
  type EvidenceTab,
  type DailyChange,
  type MarketItem,
  type MarketPayload,
  type View,
} from "./market-state";

const marketData = marketScan as unknown as MarketPayload;
const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});
const formatScanTime = (value: string) => new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
  timeZone: "America/Phoenix",
  timeZoneName: "short",
}).format(new Date(value));
const scanTime = formatScanTime(marketData.generated_at);
const navigation: { id: View; label: string; short: string }[] = [
  { id: "today", label: "Today", short: "Today" },
  { id: "market", label: "Market", short: "Market" },
  { id: "card", label: "Card Intelligence", short: "Card" },
  { id: "review", label: "Review Queue", short: "Review" },
  { id: "health", label: "Data Health", short: "Health" },
];

const formatPrice = (value?: number | null) => value == null ? "—" : money.format(value);
const formatDate = (value?: string | null) => value
  ? new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" })
    .format(new Date(`${value.slice(0, 10)}T12:00:00Z`))
  : "—";
const gradeLabel = (grade: string) => ({
  A: "Strong",
  B: "Usable",
  C: "Developing",
  D: "Weak",
  F: "Insufficient",
}[grade] ?? "Unknown");
const dispersion = (item: MarketItem) => {
  const match = item.evidence_explanation?.match(/dispersion\s+([\d.]+)%/i);
  return match ? Number(match[1]) : null;
};
const statusLabel = (item: MarketItem) => {
  if (safeAction(item)) return safeAction(item);
  if (item.scanned_this_run === false) return "ROTATES NEXT";
  if (item.fair_value != null) return "VALUE READY";
  return "EVIDENCE BUILDING";
};
const attentionReason = (item: MarketItem) => {
  if (item.scanned_this_run === false) return "Waiting for the next automatic scan rotation.";
  if ((item.review_count ?? 0) > (item.accepted_sales_total ?? 0)) {
    return `${item.review_count ?? 0} questionable matches are being kept out of the valuation.`;
  }
  if ((dispersion(item) ?? 0) >= 30) return "Accepted sales disagree too widely to support a price.";
  if ((item.accepted_sales_total ?? 0) < 8) return "More verified sales are needed before publishing a price.";
  return "Evidence is improving, but it has not cleared every trust gate.";
};
const changeLabel = (change: DailyChange) => ({
  reliable: "VALUATION CLEARED",
  weakened: "EVIDENCE WEAKENED",
  valuation: "VALUE CHANGED",
  evidence: "EVIDENCE CHANGED",
  review: "REVIEW REQUIRED",
  coverage: "COVERAGE CHANGED",
}[change.kind]);
function Grade({ value }: { value: string }) {
  return <span className={`grade grade-${value.toLowerCase()}`}><b>{value}</b>{gradeLabel(value)}</span>;
}

export default function Home() {
  const [view, setView] = useState<View>("today");
  const [query, setQuery] = useState("");
  const [sport, setSport] = useState("All");
  const [selectedCardId, setSelectedCardId] = useState(marketData.items[0]?.card_id ?? "");
  const [evidenceTab, setEvidenceTab] = useState<EvidenceTab>("accepted");
  const mainRef = useRef<HTMLElement>(null);

  const selected = getSelectedCard(marketData.items, selectedCardId);
  const sourceState = deriveMarketState(marketData);
  const evidenceLedger = selected?.evidence_ledger ?? {
    accepted: [], review: [], excluded: [],
    accepted_total: selected?.accepted_sales_total ?? 0,
    review_total: selected?.review_count ?? 0,
    excluded_total: selected?.excluded_count ?? 0,
  };
  const ledgerTotals = {
    accepted: evidenceLedger.accepted_total,
    review: evidenceLedger.review_total,
    excluded: evidenceLedger.excluded_total,
  };
  const ledgerEntries = evidenceLedger[evidenceTab];
  const ledgerTotal = ledgerTotals[evidenceTab];
  const totalAccepted = marketData.items.reduce((sum, item) => sum + (item.accepted_sales_total ?? 0), 0);
  const totalReviews = marketData.items.reduce((sum, item) => sum + (item.review_count ?? 0), 0);
  const totalExcluded = marketData.items.reduce((sum, item) => sum + (item.excluded_count ?? 0), 0);
  const scannedCount = sourceState.scannedCount;
  const actionable = marketData.items.filter(isActionable);
  const valued = marketData.items.filter((item) => item.fair_value != null);
  const priority = rankPriority(marketData.items);
  const reviewQueue = buildReviewQueue(marketData.items);
  const reviewCards = marketData.items.filter((item) => (item.review_count ?? 0) > 0);
  const dailyBrief = marketData.daily_brief ?? {
    status: "collecting" as const,
    previous_generated_at: null,
    summary: { meaningful_changes: 0, new_reliable_valuations: 0, material_valuation_changes: 0, weakened_markets: 0, new_reviews: 0, review_queue: totalReviews },
    changes: [],
  };
  const visibleItems = useMemo(() => filterMarketItems(marketData.items, query, sport), [query, sport]);
  const trustGates = selected ? valuationTrustGates(selected, marketData) : [];

  const syncRoute = useCallback(() => {
    const route = parseRoute(window.location.search, marketData.items);
    setView(route.view);
    setSelectedCardId(route.cardId);
  }, []);

  useEffect(() => {
    window.addEventListener("popstate", syncRoute);
    queueMicrotask(syncRoute);
    return () => window.removeEventListener("popstate", syncRoute);
  }, [syncRoute]);

  useEffect(() => {
    const viewTitle = view === "today"
      ? "Today"
      : view === "market"
        ? "Market"
        : view === "health"
          ? "Data Health"
          : view === "review"
            ? "Review Queue"
          : selected?.player ?? "Card Intelligence";
    document.title = `${viewTitle} — Market OS`;
  }, [selected?.player, view]);

  const navigate = (nextView: View, cardId = selectedCardId) => {
    const search = buildRouteSearch(nextView, cardId);
    const nextUrl = `${window.location.pathname}${search}`;
    if (`${window.location.pathname}${window.location.search}` !== nextUrl) {
      window.history.pushState({}, "", nextUrl);
    }
    setView(nextView);
    if (nextView === "card") setSelectedCardId(cardId);
    setEvidenceTab("accepted");
    window.scrollTo({ top: 0, behavior: "smooth" });
    window.requestAnimationFrame(() => mainRef.current?.focus({ preventScroll: true }));
  };

  const openCard = (cardId: string) => {
    navigate("card", cardId);
  };
  const openHeldEvidence = (cardId: string) => {
    navigate("card", cardId);
    setEvidenceTab("review");
  };

  return <div className="product-shell">
    <a className="skip-link" href="#main-content">Skip to market intelligence</a>
    <header className="topbar">
      <button className="brand" onClick={() => navigate("today")} aria-label="Open today's brief">
        <span>MO</span>
        <strong>Market OS<small>SPORTS CARD INTELLIGENCE</small></strong>
      </button>
      <nav className="desktop-nav" aria-label="Primary navigation">
        {navigation.map((item) => <button key={item.id} aria-current={view === item.id ? "page" : undefined} className={view === item.id ? "active" : ""} onClick={() => navigate(item.id)}>{item.label}</button>)}
      </nav>
      <div className={`connection ${sourceState.connectionTone}`}><i></i><span>{sourceState.connectionLabel}<small>{sourceState.connectionDetail} · {scanTime}</small></span></div>
    </header>

    <main id="main-content" ref={mainRef} tabIndex={-1}>
      {view === "today" && <>
        <section className="brief-hero">
          <div>
            <span className="eyebrow">TODAY&apos;S CAPITAL BRIEF · {scanTime.toUpperCase()}</span>
            <h1>{actionable.length ? `${actionable.length} action${actionable.length === 1 ? "" : "s"} cleared.` : "Today, capital stays still."}</h1>
            <p>{actionable.length
              ? "Only evidence-backed actions are shown. Open a card to inspect the full case."
              : "No monitored card has enough verified evidence to justify a price or trade. The system is showing exactly what must improve instead of manufacturing conviction."}</p>
          </div>
          <div className="decision-badge"><small>CAPITAL POSTURE</small><b>{actionable.length ? "SELECTIVE" : "NO ACTION"}</b><span>{actionable.length ? "Review cleared ideas" : "Cash is a valid position"}</span></div>
        </section>

        <section className="pulse-grid" aria-label="Market evidence summary">
          <article><small>AUTOMATIC SCAN</small><b>{scannedCount} of {marketData.items.length}</b><span>cards refreshed today</span></article>
          <article><small>VERIFIED SALES</small><b>{totalAccepted}</b><span>accepted into evidence</span></article>
          <article className="attention"><small>NEEDS ATTENTION</small><b>{totalReviews}</b><span>questionable matches isolated</span></article>
          <article><small>PRICES CLEARED</small><b>{valued.length}</b><span>trustworthy fair values</span></article>
        </section>

        <section className="delta-panel" aria-labelledby="daily-delta-heading">
          <div className="delta-heading"><div><span className="eyebrow">DAILY DELTA</span><h2 id="daily-delta-heading">What changed since the last scan</h2><p>{dailyBrief.previous_generated_at ? `Compared with ${formatScanTime(dailyBrief.previous_generated_at)}.` : "A trustworthy comparison needs two published scans."}</p></div><dl><div><dt>{dailyBrief.summary.meaningful_changes}</dt><dd>material changes</dd></div><div><dt>{dailyBrief.summary.weakened_markets}</dt><dd>weakened markets</dd></div><div><dt>{dailyBrief.summary.new_reviews}</dt><dd>new reviews</dd></div></dl></div>
          <div className="delta-list">
            {dailyBrief.changes.map((change) => <button key={change.card_id} className={`delta-row ${change.kind}`} onClick={() => openCard(change.card_id)} aria-label={`Open ${change.card} intelligence`}>
              <span className="delta-kind">{changeLabel(change)}</span>
              <span className="asset"><b>{change.player}</b><small>{change.card.replace(change.player, "").trim()}</small></span>
              <span className="delta-copy"><b>{change.headline}</b><small>{change.detail}</small></span>
              <span className="arrow">→</span>
            </button>)}
            {dailyBrief.status === "collecting" && <div className="delta-empty"><b>Daily comparison starts with the next automatic scan.</b><p>The current snapshot is now the baseline. Market OS will report only verified changes after another scan is published.</p></div>}
            {dailyBrief.status === "ready" && !dailyBrief.changes.length && <div className="delta-empty"><b>No material evidence changed.</b><p>The scan completed, but no card crossed a valuation, evidence, review, or coverage threshold.</p></div>}
          </div>
        </section>

        <section className="brief-layout">
          <div className="priority-panel">
            <div className="section-heading"><div><span>PRIORITY QUEUE</span><h2>What needs attention</h2></div><button onClick={() => navigate("review")}>Open review queue</button></div>
            {priority.map((item, index) => <button className="priority-row" key={item.card_id} aria-label={`Open ${item.card} intelligence`} onClick={() => openCard(item.card_id)}>
              <span className="priority-number">{String(index + 1).padStart(2, "0")}</span>
              <span className="asset"><b>{item.player}</b><small>{item.card.replace(item.player, "").trim()}</small></span>
              <span className="reason"><b>{statusLabel(item)}</b><small>{attentionReason(item)}</small></span>
              <Grade value={item.evidence_grade} />
              <span className="arrow">→</span>
            </button>)}
          </div>

          <aside className="trust-panel">
            <span className="eyebrow">WHY NOTHING FIRED</span>
            <h2>The restraint is the product.</h2>
            <p>Wrong comps create false prices. False prices create bad trades. Market OS is keeping weak, conflicting, and unverified evidence out of every capital decision.</p>
            <dl>
              <div><dt>{totalExcluded}</dt><dd>listings excluded</dd></div>
              <div><dt>{totalReviews}</dt><dd>matches held for review</dd></div>
              <div><dt>{actionable.length}</dt><dd>capital actions cleared</dd></div>
            </dl>
            <button onClick={() => navigate("health")}>See how evidence is graded</button>
          </aside>
        </section>
      </>}

      {view === "market" && <>
        <section className="page-title">
          <div><span className="eyebrow">MONITORED UNIVERSE · {marketData.items.length} CARDS</span><h1>Market</h1><p>Every monitored card is shown with its current evidence state. No speculative prices.</p></div>
          <div className="market-controls">
            <label><span className="sr-only">Search cards or players</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search player, card, set…" /></label>
            <select aria-label="Filter by sport" value={sport} onChange={(event) => setSport(event.target.value)}><option>All</option><option>NBA</option><option>MLB</option><option>NFL</option></select>
          </div>
        </section>
        <section className="market-list">
          <div className="market-head"><span>ASSET</span><span>STATUS</span><span>FAIR VALUE</span><span>EVIDENCE</span><span>SALES</span><span></span></div>
          {visibleItems.map((item) => <button className="market-row" key={item.card_id} aria-label={`Open ${item.card} intelligence`} onClick={() => openCard(item.card_id)}>
            <span className="asset"><b>{item.player}</b><small>{item.card.replace(item.player, "").trim()}</small></span>
            <span className={`status ${item.scanned_this_run === false ? "waiting" : ""}`}>{statusLabel(item)}</span>
            <span className="market-value"><b>{item.fair_value == null ? "Not enough evidence" : formatPrice(item.fair_value)}</b><small>{item.evidence_range ? `${formatPrice(item.evidence_range.low)}–${formatPrice(item.evidence_range.high)}` : attentionReason(item)}</small></span>
            <Grade value={item.evidence_grade} />
            <span className="sales"><b>{item.accepted_sales_total ?? 0}</b><small>{item.valuation_sample_size ?? 0} usable</small></span>
            <span className="arrow">→</span>
          </button>)}
          {!visibleItems.length && <div className="empty"><b>No monitored card matches that search.</b><button onClick={() => { setQuery(""); setSport("All"); }}>Clear filters</button></div>}
        </section>
      </>}

      {view === "card" && selected && <>
        <section className="card-title">
          <button className="back" onClick={() => navigate("market")}>← Market</button>
          <div className="card-title-row"><div><span className="eyebrow">CARD INTELLIGENCE · {selected.sport}</span><h1>{selected.card}</h1><p>Updated {scanTime}</p></div><div className="card-status"><span className={`status ${selected.scanned_this_run === false ? "waiting" : ""}`}>{statusLabel(selected)}</span><Grade value={selected.evidence_grade} /></div></div>
        </section>

        <section className="valuation-hero">
          <div className="locked-value"><small>FAIR VALUE</small><b>{selected.fair_value == null ? "Not enough evidence" : formatPrice(selected.fair_value)}</b><p>{selected.fair_value == null ? "A price will appear only after the evidence clears every trust gate." : selected.thesis}</p></div>
          <div className="confidence-ring" style={{ "--score": `${selected.confidence * 3.6}deg` } as React.CSSProperties}><span><b>{selected.confidence}%</b><small>confidence</small></span></div>
        </section>

        <section className="evidence-chain">
          <article><small>01 · ACCEPTED</small><b>{selected.accepted_sales_total ?? 0} sales</b><p>Matched to the canonical card and eligible for consideration.</p></article>
          <i>→</i>
          <article><small>02 · VALUATION SAMPLE</small><b>{selected.valuation_sample_size ?? 0} sales</b><p>Remaining after robust outlier filtering.</p></article>
          <i>→</i>
          <article className={selected.fair_value == null ? "locked" : "cleared"}><small>03 · DISPLAY GATE</small><b>{selected.fair_value == null ? "Locked" : "Cleared"}</b><p>{selected.fair_value == null ? "The evidence is not strong enough to publish a price." : "A fair value can be shown."}</p></article>
        </section>

        <section className="trust-gates" aria-labelledby="trust-gates-heading">
          <div className="trust-gates-heading"><span className="eyebrow">TRUST GATES</span><h2 id="trust-gates-heading">Exactly what has cleared</h2><p>A valuation and a capital action use separate gates. Waiting is not the same as failing.</p></div>
          <div className="trust-gate-list">
            {trustGates.map((gate) => <article className={`trust-gate ${gate.state}`} key={gate.id}>
              <span aria-hidden="true">{gate.state === "pass" ? "✓" : gate.state === "waiting" ? "…" : "×"}</span>
              <div><small>{gate.label}</small><b>{gate.value}</b><p>{gate.detail}</p></div>
            </article>)}
          </div>
        </section>

        <section className="card-grid">
          <div className="why-panel">
            <span className="eyebrow">THE EVIDENCE CASE</span>
            <h2>Why this card should—or should not—be trusted</h2>
            <p>{selected.evidence_explanation ?? selected.thesis}</p>
            {(selected.blockers ?? []).length > 0
              ? <div className="blocker-list"><b>What must change</b>{(selected.blockers ?? []).map((blocker) => <span key={blocker}>{plainBlocker(blocker)}</span>)}</div>
              : <div className="cleared-list"><b>Why it cleared</b><span>Every current valuation gate passed. Continue to monitor new evidence and invalidation conditions.</span></div>}
          </div>
          <aside className="facts-panel">
            <h3>Evidence facts</h3>
            <dl>
              <div><dt>Latest verified sale</dt><dd>{formatDate(selected.latest_sale_date)}</dd></div>
              <div><dt>Sales in 30 days</dt><dd>{selected.accepted_sales_30d}</dd></div>
              <div><dt>Needs review</dt><dd>{selected.review_count ?? 0}</dd></div>
              <div><dt>Excluded listings</dt><dd>{selected.excluded_count ?? 0}</dd></div>
              <div><dt>Dispersion</dt><dd>{dispersion(selected) == null ? "—" : `${dispersion(selected)}%`}</dd></div>
              <div><dt>Scan state</dt><dd>{selected.scanned_this_run ? "Complete" : "Scheduled later"}</dd></div>
            </dl>
            <label>Switch card<select value={selected.card_id} onChange={(event) => openCard(event.target.value)}>{marketData.items.map((item) => <option key={item.card_id} value={item.card_id}>{item.player} · {item.card.split("·").at(-1)?.trim()}</option>)}</select></label>
          </aside>
        </section>

        <section className="evidence-ledger">
          <div className="ledger-heading">
            <div><span className="eyebrow">COMP EVIDENCE</span><h2>Audit the valuation</h2><p>See exactly what entered the evidence set, what was held back, and why.</p></div>
            <div className="ledger-tabs" role="group" aria-label="Filter comp evidence">
              {(["accepted", "review", "excluded"] as EvidenceTab[]).map((tab) => <button key={tab} aria-pressed={evidenceTab === tab} className={evidenceTab === tab ? "active" : ""} onClick={() => setEvidenceTab(tab)}>
                {tab === "accepted" ? "Accepted" : tab === "review" ? "Held for review" : "Excluded"}
                <b>{ledgerTotals[tab]}</b>
              </button>)}
            </div>
          </div>
          <div className="ledger-list">
            {ledgerEntries.map((entry) => <article className="ledger-row" key={entry.evidence_id}>
              <div className="ledger-state"><span className={`evidence-pill ${entry.status}`}>{entry.status === "accepted" ? entry.used_in_valuation ? "USED" : "FILTERED" : entry.status === "review" ? "HELD" : "EXCLUDED"}</span><small>{entry.source}</small></div>
              <div className="ledger-title"><b>{entry.title}</b><span>{entry.reason}</span></div>
              <div className="ledger-facts"><b>{entry.price == null ? "Price withheld" : formatPrice(entry.price)}</b><small>{formatDate(entry.event_date)}</small></div>
              {entry.url ? <a href={entry.url} target="_blank" rel="noreferrer" aria-label={`Open source listing for ${entry.title}`}>View source ↗</a> : <span className="source-unavailable">Source link unavailable</span>}
            </article>)}
            {!ledgerEntries.length && <div className="ledger-empty"><b>{ledgerTotal ? "The published snapshot does not contain these audit rows yet." : `No ${evidenceTab === "review" ? "held" : evidenceTab} comps for this card.`}</b><p>{ledgerTotal ? `The scan reports ${ledgerTotal} ${evidenceTab === "review" ? "held" : evidenceTab} comps. The next successfully published scan will replace this count-only fallback with the actual evidence rows.` : "Nothing is being hidden from this category."}</p></div>}
          </div>
          {ledgerEntries.length < ledgerTotal && ledgerEntries.length > 0 && <p className="ledger-note">Showing {ledgerEntries.length} of {ledgerTotal}. The most recent evidence is shown first.</p>}
        </section>
      </>}

      {view === "review" && <>
        <section className="page-title review-title"><div><span className="eyebrow">EVIDENCE OPERATIONS</span><h1>Review Queue</h1><p>Questionable matches remain outside every valuation until their card identity is resolved.</p></div><div className="review-count"><small>UNRESOLVED</small><b>{totalReviews}</b><span>{reviewQueue.length ? `${reviewQueue.length} listing rows available` : "rows arrive with the next scan"}</span></div></section>
        <section className="review-policy" aria-label="Review queue policy"><b>Public, read-only evidence triage</b><p>This surface exposes what is blocking valuations without letting anonymous visitors alter the canonical registry. Final Approve, Reject, and Choose another card controls remain operator-only.</p></section>
        <section className="review-queue">
          <div className="review-head"><span>HELD LISTING</span><span>PROPOSED CANONICAL CARD</span><span>WHY IT IS HELD</span><span>ACTIONS</span></div>
          {reviewQueue.map((entry) => <article className="review-row" key={`${entry.card_id}:${entry.evidence_id}`}>
            <div className="held-listing"><span className="evidence-pill review">HELD</span><b>{entry.title}</b><small>{entry.source} · {entry.price == null ? "price withheld" : formatPrice(entry.price)} · {formatDate(entry.event_date)}</small></div>
            <div className="proposed-card"><b>{entry.player}</b><span>{entry.card.replace(entry.player, "").trim()}</span><small>{entry.sport} · Evidence grade {marketData.items.find((item) => item.card_id === entry.card_id)?.evidence_grade}</small></div>
            <div className="review-reason"><b>Identity conflict</b><p>{entry.reason}</p></div>
            <div className="review-actions"><button onClick={() => openHeldEvidence(entry.card_id)}>Inspect match</button>{entry.url ? <a href={entry.url} target="_blank" rel="noreferrer">Source ↗</a> : <span>Source unavailable</span>}</div>
          </article>)}
          {!reviewQueue.length && reviewCards.map((item) => <article className="review-row count-only" key={item.card_id}>
            <div className="held-listing"><span className="evidence-pill review">HELD</span><b>{item.review_count} questionable matches</b><small>Detailed listing rows are not present in this older public snapshot.</small></div>
            <div className="proposed-card"><b>{item.player}</b><span>{item.card.replace(item.player, "").trim()}</span><small>{item.sport} · Evidence grade {item.evidence_grade}</small></div>
            <div className="review-reason"><b>Waiting for row-level evidence</b><p>The next successfully published scan will attach the actual held listings and reasons.</p></div>
            <div className="review-actions"><button onClick={() => openHeldEvidence(item.card_id)}>Inspect card</button></div>
          </article>)}
          {!totalReviews && <div className="review-empty"><b>The review queue is clear.</b><p>No questionable card matches are currently blocking monitored valuations.</p></div>}
        </section>
      </>}

      {view === "health" && <>
        <section className="page-title"><div><span className="eyebrow">SYSTEM TRANSPARENCY</span><h1>Data Health</h1><p>What ran, what was trusted, and what was kept out.</p></div><div className={`health-state ${sourceState.connectionTone}`}><i></i><span>{sourceState.connectionLabel}<b>{sourceState.connectionDetail}</b></span></div></section>
        <section className="health-grid">
          <article className="source-card"><span className="eyebrow">EVIDENCE SOURCE</span><h2>Public eBay sold results</h2><p>Market OS collects evidence automatically. You do not need to upload exports or manage raw files.</p><dl><div><dt>Cadence</dt><dd>Daily automatic scan</dd></div><div><dt>Currency</dt><dd>USD only</dd></div><div><dt>Best Offers</dt><dd>Excluded</dd></div><div><dt>Maximum grade</dt><dd>B until independently confirmed</dd></div></dl></article>
          <article className="run-card"><span className="eyebrow">LATEST RUN</span><h2>{scannedCount} of {marketData.items.length} cards scanned</h2><p>{sourceState.deferredCount
            ? `${sourceState.deferredCount} card${sourceState.deferredCount === 1 ? " was" : "s were"} deferred by the source rotation. Deferred cards are labeled—not mistaken for markets with no sales.`
            : sourceState.failedCount
              ? `${sourceState.failedCount} card${sourceState.failedCount === 1 ? "" : "s"} could not be refreshed and will not be treated as a market with no sales.`
              : "Every monitored card completed its scheduled evidence scan."}</p><div className="run-meter"><i style={{ width: `${marketData.items.length ? (scannedCount / marketData.items.length) * 100 : 0}%` }}></i></div><small>Last completed {scanTime}</small></article>
          <article className="guardrail-card"><span className="eyebrow">GUARDRAILS</span><h2>Weak evidence cannot become a trade.</h2><ul><li>Questionable identity matches stay outside valuation.</li><li>Extreme prices are removed from the valuation sample.</li><li>Insufficient evidence displays “Not enough evidence.”</li><li>Capital actions require forward calibration.</li></ul></article>
        </section>
        <section className="grade-guide"><div><span className="eyebrow">EVIDENCE GRADES</span><h2>How to read the market</h2></div>{[["A", "Strong", "Deep, recent, consistent evidence."], ["B", "Usable", "Good evidence with controlled limitations."], ["C", "Developing", "Useful context, not ready for capital."], ["D", "Weak", "Sparse or inconsistent evidence."], ["F", "Insufficient", "No trustworthy valuation can be shown."]].map(([grade, title, description]) => <article key={grade}><Grade value={grade} /><b>{title}</b><p>{description}</p></article>)}</section>
      </>}
    </main>

    <nav className="mobile-nav" aria-label="Mobile navigation">
      {navigation.map((item) => <button key={item.id} aria-current={view === item.id ? "page" : undefined} className={view === item.id ? "active" : ""} onClick={() => navigate(item.id)}>{item.short}</button>)}
    </nav>
  </div>;
}
