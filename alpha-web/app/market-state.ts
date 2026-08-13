export type View = "today" | "market" | "card" | "health";
export type EvidenceRange = { low: number; high: number } | null;
export type EvidenceTab = "accepted" | "review" | "excluded";
export type EvidenceLedgerEntry = {
  evidence_id: string;
  status: "accepted" | "review" | "rejected";
  title: string;
  price: number | null;
  currency: "USD" | null;
  event_date: string | null;
  source: string;
  url: string | null;
  used_in_valuation: boolean;
  reason: string;
};
export type EvidenceLedger = {
  accepted: EvidenceLedgerEntry[];
  review: EvidenceLedgerEntry[];
  excluded: EvidenceLedgerEntry[];
  accepted_total: number;
  review_total: number;
  excluded_total: number;
};

export type MarketItem = {
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
  valuation_sample_size?: number;
  accepted_active_count?: number;
  review_count?: number;
  excluded_count?: number;
  lowest_ask?: number | null;
  median_ask?: number | null;
  latest_sale_date?: string | null;
  last_updated?: string;
  scanned_this_run?: boolean;
  scan_state?: "complete" | "deferred_rotation" | "failed" | "unavailable" | "unknown";
  ideal_entry?: number | null;
  do_not_chase?: number | null;
  thesis: string;
  evidence_explanation?: string;
  blockers?: string[];
  evidence_ledger?: EvidenceLedger;
};

export type MarketPayload = {
  generated_at: string;
  source: {
    kind: string;
    label: string;
    provenance?: {
      sold_source_available?: boolean;
      listing_source_available?: boolean;
      evidence_grade_cap?: string;
      sold_provider?: string;
      errors?: string[];
    };
  };
  universe_size: number;
  items: MarketItem[];
};

const TRUSTED_ACTION_GRADES = new Set(["A", "B"]);
const MAX_CURRENT_AGE_MS = 36 * 60 * 60 * 1000;

export function isActionable(item: MarketItem) {
  const hasClosedGate = (item.blockers ?? []).some((blocker) => (
    /valuation gate|forward calibration|unavailable/i.test(blocker)
  ));
  return Boolean(
    item.action
    && item.fair_value != null
    && TRUSTED_ACTION_GRADES.has(item.evidence_grade)
    && !hasClosedGate
  );
}

export function safeAction(item: MarketItem) {
  return isActionable(item) ? item.action : null;
}

export function filterMarketItems(items: MarketItem[], query: string, sport: string) {
  const needle = query.trim().toLowerCase();
  return items.filter((item) => (
    (sport === "All" || item.sport === sport)
    && (!needle || [item.player, item.card, item.card_id, item.sport]
      .some((value) => value.toLowerCase().includes(needle)))
  ));
}

export function rankPriority(items: MarketItem[]) {
  return [...items].sort((left, right) => (
    (right.review_count ?? 0) - (left.review_count ?? 0)
    || right.confidence - left.confidence
  ));
}

export function getSelectedCard(items: MarketItem[], cardId: string) {
  return items.find((item) => item.card_id === cardId) ?? items[0];
}

export function deriveMarketState(payload: MarketPayload, now = Date.now()) {
  const generatedAt = Date.parse(payload.generated_at);
  const age = now - generatedAt;
  const soldAvailable = payload.source.provenance?.sold_source_available === true;
  const errors = payload.source.provenance?.errors ?? [];
  const scannedCount = payload.items.filter((item) => item.scanned_this_run).length;
  const deferredCount = payload.items.filter((item) => item.scan_state === "deferred_rotation").length;
  const failedCount = payload.items.filter((item) => ["failed", "unavailable"].includes(item.scan_state ?? "")).length;
  const current = Number.isFinite(generatedAt) && age >= 0 && age <= MAX_CURRENT_AGE_MS;

  if (!soldAvailable || failedCount > 0) {
    return {
      connectionLabel: "EVIDENCE OFFLINE",
      connectionDetail: "Sold evidence needs attention",
      connectionTone: "offline",
      soldAvailable,
      current,
      scannedCount,
      deferredCount,
      failedCount,
      errors,
    } as const;
  }

  if (!current) {
    return {
      connectionLabel: "STALE SNAPSHOT",
      connectionDetail: "A new scan is overdue",
      connectionTone: "stale",
      soldAvailable,
      current,
      scannedCount,
      deferredCount,
      failedCount,
      errors,
    } as const;
  }

  return {
    connectionLabel: errors.length ? "PARTIAL EVIDENCE" : "CURRENT EVIDENCE",
    connectionDetail: errors.length ? "Some collection work failed" : "Automatic scan completed",
    connectionTone: errors.length ? "stale" : "current",
    soldAvailable,
    current,
    scannedCount,
    deferredCount,
    failedCount,
    errors,
  } as const;
}

export function plainBlocker(blocker: string) {
  if (blocker.includes("free-plan rotation") || blocker.includes("later free-plan rotation")) return "This card will be collected on a later automatic scan.";
  if (blocker.includes("valuation gate")) return "More consistent verified sales are required.";
  if (blocker.includes("capped at evidence grade")) return "This public source can reach grade B at best until a second source agrees.";
  if (blocker.includes("Forward calibration")) return "Future sales have not yet verified the model's estimate.";
  if (blocker.includes("unavailable")) return "Confirmed sold evidence is currently unavailable.";
  return blocker;
}
