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