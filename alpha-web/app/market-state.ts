export type View = "today" | "market" | "card" | "review" | "health";
export type RouteState = { view: View; cardId: string };
export type TrustGate = {
  id: string;
  label: string;
  value: string;
  state: "pass" | "fail" | "waiting";
  detail: string;
};
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
export type DailyChange = {
  card_id: string;
  player: string;
  card: string;
  kind: "reliable" | "weakened" | "valuation" | "evidence" | "review" | "coverage";
  headline: string;
  detail: string;
  accepted_sales_delta: number;
  valuation_sample_delta: number;
  review_delta: number;
  fair_value_delta: number | null;
  fair_value_delta_pct: number | null;
  evidence_grade_from: string | null;
  evidence_grade_to: string;
};
export type DailyBrief = {
  status: "collecting" | "ready";
  previous_generated_at: string | null;
  summary: {
    meaningful_changes: number;
    new_reliable_valuations: number;
    material_valuation_changes: number;
    weakened_markets: number;
    new_reviews: number;
    review_queue: number;
  };
  changes: DailyChange[];
};
export type ReviewQueueEntry = EvidenceLedgerEntry & {
  card_id: string;
  card: string;
  player: string;
  sport: string;
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
  daily_brief?: DailyBrief;
  items: MarketItem[];
};

const TRUSTED_ACTION_GRADES = new Set(["A", "B"]);
const MAX_CURRENT_AGE_MS = 36 * 60 * 60 * 1000;
const VIEWS = new Set<View>(["today", "market", "card", "review", "health"]);

export function parseRoute(search: string, items: MarketItem[]): RouteState {
  const params = new URLSearchParams(search);
  const requestedView = params.get("view") as View | null;
  const requestedCardId = params.get("card") ?? "";
  const fallbackCardId = items[0]?.card_id ?? "";
  const cardId = items.some((item) => item.card_id === requestedCardId)
    ? requestedCardId
    : fallbackCardId;

  return {
    view: requestedView && VIEWS.has(requestedView) ? requestedView : "today",
    cardId,
  };
}

export function buildRouteSearch(view: View, cardId = "") {
  if (view === "today") return "";
  const params = new URLSearchParams({ view });
  if (view === "card" && cardId) params.set("card", cardId);
  return `?${params.toString()}`;
}

export function valuationTrustGates(item: MarketItem, payload: MarketPayload): TrustGate[] {
  const soldAvailable = payload.source.provenance?.sold_source_available === true;
  const scanned = item.scanned_this_run === true;
  const sampleSize = item.valuation_sample_size ?? 0;
  const trustedGrade = TRUSTED_ACTION_GRADES.has(item.evidence_grade);
  const calibrated = !((item.blockers ?? []).some((blocker) => /forward calibration/i.test(blocker)));

  return [
    {
      id: "source",
      label: "Confirmed sold source",
      value: soldAvailable ? "Available" : "Unavailable",
      state: soldAvailable ? "pass" : "fail",
      detail: soldAvailable ? "Sold observations were available to the scan." : "No valuation can clear without confirmed sold evidence.",
    },
    {
      id: "scan",
      label: "Current card scan",
      value: scanned ? "Complete" : "Waiting",
      state: scanned ? "pass" : "waiting",
      detail: scanned ? "This card was refreshed in the latest run." : "This card is scheduled for a later source rotation.",
    },
    {
      id: "sample",
      label: "Usable valuation sample",
      value: `${sampleSize} / 8 required`,
      state: sampleSize >= 8 ? "pass" : "fail",
      detail: sampleSize >= 8 ? "Enough consistent sales remain after filtering." : "More verified sales must survive identity and outlier checks.",
    },
    {
      id: "grade",
      label: "Evidence quality",
      value: `${item.evidence_grade} · ${TRUSTED_ACTION_GRADES.has(item.evidence_grade) ? "cleared" : "below B"}`,
      state: trustedGrade ? "pass" : "fail",
      detail: trustedGrade ? "Evidence quality is sufficient to display a valuation." : "Recency, depth, or consistency is still too weak.",
    },
    {
      id: "calibration",
      label: "Forward action calibration",
      value: calibrated ? "Cleared" : "Waiting",
      state: calibrated ? "pass" : "waiting",
      detail: calibrated ? "Matured outcomes support capital guidance." : "Future sales must verify estimates before BUY or SELL guidance appears.",
    },
  ];
}

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

export function buildReviewQueue(items: MarketItem[]) {
  return items.flatMap((item) => (item.evidence_ledger?.review ?? []).map((entry) => ({
    ...entry,
    card_id: item.card_id,
    card: item.card,
    player: item.player,
    sport: item.sport,
  }))).sort((left, right) => (
    String(right.event_date ?? "").localeCompare(String(left.event_date ?? ""))
    || left.player.localeCompare(right.player)
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
