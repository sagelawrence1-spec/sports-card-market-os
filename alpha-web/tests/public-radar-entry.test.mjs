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
  assert.equal(queue.requested_count, radarFeed.candidates.length);
  assert.equal(queue.items.length, radarFeed.candidates.length);
  assert.deepEqual(
    queue.items.map((item) => item.card_id),
    radarFeed.candidates.map((candidate) => candidate.card_id),
  );
  assert.ok(queue.items.every((item) => item.status === "MISSING_EXPORT"));
  assert.ok(queue.items.every((item) => item.expected_export_filename.endsWith(".csv")));
  assert.match(radarSource, /eBay Product Research queue/);
  assert.match(radarSource, /EXPECTED EXPORT/);
  assert.match(radarSource, /EXPORTS MISSING/);
});
