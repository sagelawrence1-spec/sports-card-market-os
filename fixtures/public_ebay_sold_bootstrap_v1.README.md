# Public eBay sold bootstrap corpus v1

This fixture is a deliberately limited empirical bootstrap for entity-resolution measurement when authenticated eBay Product Research access is unavailable.

- Every row references a genuine public `ebay.com/itm/...` listing page.
- Ground truth is card-identity relevance to the canonical Opportunity asset, not whether the listing price is authoritative.
- Hard negatives intentionally include graded slabs, parallels, serial-numbered variants, wrong-year/set evidence, and alternate inserts.
- Public SOLD pages are **not** treated as equivalent to eBay Product Research. Best Offer or otherwise ambiguous realized prices are excluded from valuation use.
- Exact visible sold price + shipping rows may be used only as a limited price sanity subset.
- Production-readiness thresholds remain: zero observed false accepts, >=99% precision, >=80% recall, and <=35% review burden. The first measured baseline is intentionally preserved even when it fails those thresholds.

The corpus exists to expose observed matcher failures and drive evidence-based fixes, not to manufacture a passing score.
