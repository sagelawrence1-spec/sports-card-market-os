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
  assert.match(html, /VERIFIED SALES/);
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
  assert.match(page, /Review Queue/);
  assert.match(page, /What changed since the last scan/);
  assert.match(page, /Public, read-only evidence triage/);
  assert.match(page, /buildReviewQueue/);
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
  assert.match(page, /window\.history\.pushState/);
  assert.match(page, /parseRoute/);
  assert.match(page, /aria-current/);
  assert.match(page, /deriveMarketState/);
  assert.match(page, /isActionable/);
  assert.match(page, /Audit the valuation/);
  assert.match(page, /Held for review/);
  assert.match(page, /View source/);
  assert.match(page, /aria-pressed/);
  assert.match(page, /next successfully published scan/);
  assert.match(page, /Exactly what has cleared/);
  assert.match(page, /Skip to market intelligence/);
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

test("a successful scheduled scan persists history and triggers the normal public deployment", async () => {
  const workflow = await readFile(new URL("../../.github/workflows/market-scan.yml", import.meta.url), "utf8");
  const pagesWorkflow = await readFile(new URL("../../.github/workflows/pages.yml", import.meta.url), "utf8");
  assert.match(workflow, /market_runner\.py/);
  assert.match(workflow, /contents: write/);
  assert.match(workflow, /actions\/cache@v4/);
  assert.match(workflow, /market-history\.json/);
  assert.match(workflow, /git push origin HEAD:main/);
  assert.match(pagesWorkflow, /branches: \[main\]/);
  assert.match(pagesWorkflow, /actions\/deploy-pages@v4/);
});

test("tablet widths retain a visible primary navigation surface", async () => {
  const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");
  assert.match(css, /@media\(min-width:761px\) and \(max-width:1050px\)/);
  assert.match(css, /@media\(min-width:761px\) and \(max-width:1050px\)\{[^}]*main\{padding-bottom:92px\}\.mobile-nav\{[^}]*display:grid/);
  assert.match(css, /grid-template-columns:repeat\(5,1fr\)/);
});
