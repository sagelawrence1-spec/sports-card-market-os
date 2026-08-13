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

test("server-renders the usable daily capital brief", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>Market OS — Know When the Evidence Is Ready<\/title>/i);
  assert.match(html, /Today, capital stays still/);
  assert.match(html, /CURRENT EVIDENCE/);
  assert.match(html, /What needs attention/);
  assert.match(html, /Shohei Ohtani/);
  assert.doesNotMatch(html, /\/Users\//);
  assert.match(html, /The restraint is the product/);
});

test("ships only working product surfaces without speculative features", async () => {
  const [page, layout, packageJson] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);
  assert.match(page, /Today/);
  assert.match(page, /Market/);
  assert.match(page, /Card Intelligence/);
  assert.match(page, /Data Health/);
  assert.match(page, /market-scan\.json/);
  assert.match(page, /Not enough evidence/);
  assert.match(page, /selectedCardId/);
  assert.match(page, /accepted_sales_total/);
  assert.match(page, /valuation_sample_size/);
  assert.match(page, /ROTATES NEXT/);
  assert.match(page, /What must change/);
  assert.match(page, /You do not need to upload exports/);
  assert.match(page, /setQuery/);
  assert.match(page, /window\.scrollTo/);
  assert.match(page, /aria-current/);
  assert.match(page, /deriveMarketState/);
  assert.match(page, /isActionable/);
  assert.match(page, /Audit the valuation/);
  assert.match(page, /Held for review/);
  assert.match(page, /View source/);
  assert.match(page, /aria-pressed/);
  assert.match(page, /predates the auditable ledger format/);
  assert.match(page, /Cash is a valid position/);
  assert.doesNotMatch(page, /unsupported actions shown/);
  assert.doesNotMatch(page, /One card was deferred/);
  assert.doesNotMatch(page, /Opportunity Feed/);
  assert.doesNotMatch(page, /Portfolio/);
  assert.doesNotMatch(page, /Player Market/);
  assert.doesNotMatch(page, /only remaining input/);
  assert.doesNotMatch(page, /const signals=\[/);
  assert.match(layout, /Know When the Evidence Is Ready/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
});
