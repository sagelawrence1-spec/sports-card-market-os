import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("GitHub Pages build exposes the Opportunity Radar surface", async () => {
  const [entry, radar] = await Promise.all([
    readFile(new URL("../public-app/main.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/radar/page.tsx", import.meta.url), "utf8"),
  ]);

  assert.match(entry, /import RadarPage from "\.\.\/app\/radar\/page"/);
  assert.match(entry, /window\.location\.hash === "#radar"/);
  assert.match(entry, /href="#radar"/);
  assert.match(entry, /<RadarPage \/>/);
  assert.match(radar, /LIVE WATCHES/);
  assert.match(radar, /WATCH FOR COMPS/);
  assert.match(radar, /authoritative eBay Product Research comps/i);
});

test("public Radar exposes the exact authoritative research queue", async () => {
  const [radarSource, radarFeedRaw, queueRaw] = await Promise.all([
    readFile(new URL("../app/radar/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../public/data/opportunity-radar.json", import.meta.url), "utf8"),
    readFile(new URL("../public/data/opportunity-research-queue.json", import.meta.url), "utf8"),
  ]);
  const radarFeed = JSON.parse(radarFeedRaw);
  const queue = JSON.parse(queueRaw);

  assert.equal(queue.schema, "opportunity-research-queue-public.v1");
  assert.equal(queue.source_type, "EBAY_PRODUCT_RESEARCH");
  assert.equal(queue.source_radar_generated_at, radarFeed.generated_at);
  assert.equal(queue.requested_count, 6);
  assert.equal(queue.requested_count, radarFeed.candidates.length);
  assert.equal(queue.items.length, radarFeed.candidates.length);
  assert.deepEqual(
    queue.items.map((item) => item.card_id),
    radarFeed.candidates.map((candidate) => candidate.card_id),
  );
  assert.ok(queue.items.every((item) => item.status === "MISSING_EXPORT"));
  assert.ok(queue.items.every((item) => item.expected_export_filename.endsWith(".csv")));
  assert.ok(queue.items.every((item) => typeof item.search_query === "string" && item.search_query.length > 20));
  assert.deepEqual(
    queue.items.map((item) => item.search_query),
    [
      "2025 Elian Pena Bowman Chrome CPA-EP autograph",
      "2024 George Wolkow Bowman Chrome CPA-GWO autograph",
      "2025 Kaytron Allen Bowman Chrome University BCA-KA autograph",
      "2025 Franklin Arias Bowman Chrome CPA-FA autograph",
      "2025 Bo Davidson Bowman Chrome CPA-BD autograph",
      "2024 Caleb Bonemer Bowman Draft Chrome CPA-CBO autograph",
    ],
  );
  assert.deepEqual(
    radarFeed.candidates.slice(3).map((candidate) => candidate.player_id),
    ["mlb-franklin-arias", "mlb-bo-davidson", "mlb-caleb-bonemer"],
  );
  assert.ok(radarFeed.candidates.every((candidate) => candidate.decision === "WATCH_FOR_COMPS"));
  assert.match(radarSource, /eBay Product Research queue/);
  assert.match(radarSource, /PRODUCT RESEARCH QUERY/);
  assert.match(radarSource, /EXPECTED EXPORT/);
  assert.match(radarSource, /EXPORTS MISSING/);
});