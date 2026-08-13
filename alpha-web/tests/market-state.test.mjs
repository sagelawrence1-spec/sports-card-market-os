import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  buildRouteSearch,
  deriveMarketState,
  filterMarketItems,
  getSelectedCard,
  isActionable,
  parseRoute,
  plainBlocker,
  rankPriority,
  safeAction,
  valuationTrustGates,
} from "../app/market-state.ts";

const marketData = JSON.parse(await readFile(new URL("../public/data/market-scan.json", import.meta.url), "utf8"));

test("search and sport filters behave like the market screen", () => {
  assert.deepEqual(filterMarketItems(marketData.items, "ohtani", "All").map((item) => item.player), ["Shohei Ohtani"]);
  assert.deepEqual(filterMarketItems(marketData.items, "silver", "NBA").map((item) => item.player), ["Victor Wembanyama"]);
  assert.equal(filterMarketItems(marketData.items, "does not exist", "All").length, 0);
});

test("card selection falls back safely and priority reflects review burden", () => {
  assert.equal(getSelectedCard(marketData.items, "CURRY-2009-TOPPS-CHROME-101-PSA9").player, "Stephen Curry");
  assert.equal(getSelectedCard(marketData.items, "missing-card").player, "Shohei Ohtani");
  assert.equal(rankPriority(marketData.items)[0].player, "Shohei Ohtani");
});

test("contradictory evidence can never surface a capital action", () => {
  const base = { ...marketData.items[0], action: "BUY", fair_value: 500, evidence_grade: "B", blockers: [] };
  assert.equal(isActionable(base), true);
  assert.equal(safeAction(base), "BUY");
  assert.equal(isActionable({ ...base, fair_value: null }), false);
  assert.equal(isActionable({ ...base, evidence_grade: "C" }), false);
  assert.equal(isActionable({ ...base, blockers: ["Forward calibration has not cleared the action gate"] }), false);
});

test("data-health labels are derived from real freshness and availability", () => {
  const generatedAt = Date.parse(marketData.generated_at);
  const current = deriveMarketState(marketData, generatedAt + 60 * 60 * 1000);
  assert.equal(current.connectionLabel, "CURRENT EVIDENCE");
  assert.equal(current.scannedCount, 3);
  assert.equal(current.deferredCount, 1);

  const stale = deriveMarketState(marketData, generatedAt + 48 * 60 * 60 * 1000);
  assert.equal(stale.connectionLabel, "STALE SNAPSHOT");

  const offlinePayload = structuredClone(marketData);
  offlinePayload.source.provenance.sold_source_available = false;
  assert.equal(deriveMarketState(offlinePayload, generatedAt).connectionLabel, "EVIDENCE OFFLINE");
});

test("technical blockers are translated into collector language", () => {
  assert.equal(
    plainBlocker("Scheduled for a later free-plan rotation; no sold query ran for this card today"),
    "This card will be collected on a later automatic scan.",
  );
  assert.equal(
    plainBlocker("Forward calibration has not cleared the action gate"),
    "Future sales have not yet verified the model's estimate.",
  );
});

test("shareable routes preserve valid views and card identity", () => {
  const curryId = "CURRY-2009-TOPPS-CHROME-101-PSA9";
  assert.equal(buildRouteSearch("today"), "");
  assert.equal(buildRouteSearch("market"), "?view=market");
  assert.equal(buildRouteSearch("card", curryId), `?view=card&card=${curryId}`);
  assert.deepEqual(parseRoute(`?view=card&card=${curryId}`, marketData.items), {
    view: "card",
    cardId: curryId,
  });
  assert.deepEqual(parseRoute("?view=unknown&card=missing", marketData.items), {
    view: "today",
    cardId: marketData.items[0].card_id,
  });
});

test("trust gates name the exact valuation and action blockers", () => {
  const gates = valuationTrustGates(marketData.items[0], marketData);
  assert.deepEqual(gates.map((gate) => gate.id), ["source", "scan", "sample", "grade", "calibration"]);
  assert.equal(gates.find((gate) => gate.id === "source").state, "pass");
  assert.equal(gates.find((gate) => gate.id === "sample").value, "4 / 8 required");
  assert.equal(gates.find((gate) => gate.id === "sample").state, "fail");
  assert.equal(gates.find((gate) => gate.id === "calibration").state, "waiting");
});
