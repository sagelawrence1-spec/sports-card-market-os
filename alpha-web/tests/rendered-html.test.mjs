import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";


async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the first confirmed evidence scan", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>Market OS — Sports Card Intelligence<\/title>/i);
  assert.match(html, /Market Scan/);
  assert.match(html, /Highest-conviction changes/);
  assert.match(html, /Shohei Ohtani/);
  assert.match(html, /LIVE EVIDENCE/);
  assert.match(html, /Not enough evidence/);
});

test("ships evidence-first product language without starter artifacts", async () => {
  const [page, layout, packageJson] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);
  assert.match(page, /Opportunity Feed/);
  assert.match(page, /Player Market/);
  assert.match(page, /CAPITAL ALLOCATOR/);
  assert.match(page, /Evidence Desk/);
  assert.match(page, /market-scan\.json/);
  assert.match(page, /Not enough evidence/);
  assert.match(page, /selectedCardId/);
  assert.match(page, /accepted_sales_total/);
  assert.match(page, /valuation_sample_size/);
  assert.match(page, /rotates next run/);
  assert.match(page, /Before capital can move/);
  assert.match(page, /No opportunity clears the evidence and calibration gates/);
  assert.match(page, /setQuery/);
  assert.match(page, /No capital action is authorized/);
  assert.doesNotMatch(page, /only remaining input/);
  assert.doesNotMatch(page, /const signals=\[/);
  assert.match(layout, /Sports Card Intelligence/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
});
