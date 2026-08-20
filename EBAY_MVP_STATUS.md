# eBay MVP Status — v0.6

## Implemented
- Official eBay Browse API adapter for live listings/supply.
- OAuth client-credentials token flow using environment variables; secrets are never stored in source.
- eBay Product Research structured-ingestion adapter for authoritative historical sales extracts.
- Marketplace Insights provider boundary, ready to replace the fallback if approved access exists.
- Automatic SoldComps public-result adapter with grouped query rotation, strict Best Offer rejection, buyer-cost normalization, and evidence-grade ceiling.
- Sports-card-specific entity matcher with hard rejection of common comp contamination:
  - wrong player
  - wrong card number
  - wrong grading company
  - raw vs graded mismatch
  - wrong parallel / base-vs-parallel
  - reprints / facsimiles / customs / digital cards
  - multi-card lots and break spots
- Immutable evidence store preserving accepted, rejected, and review records with raw payload and match diagnostics.
- Materialization step that permits only accepted evidence to enter normalized sales/listing history.
- Genuine public-eBay SOLD bootstrap corpus across the six current Opportunity assets.
- Expanded 30-row genuine public-eBay identity corpus with five labeled rows per canonical card and at least two positive plus two negative examples per card.
- Leakage-safe empirical matcher evaluation reporting overall, family, and per-card metrics plus decision-reason histograms.
- Public-eBay corpus health gate separating matcher quality, corpus breadth, and Product Research price authority.
- Explicit evidence roles preventing identity-only public item pages from being escalated into price evidence.

## Current measured identity proof
The first 15-row genuine public SOLD bootstrap exposed a real matcher recall failure instead of manufacturing a pass. Observed-data fixes corrected those misses while retaining zero observed false accepts.

The evidence set was then doubled to 30 genuine public eBay pages, balanced across all six current canonical Opportunity assets. That broader corpus exposed another real recall defect: eBay product titles using the plural `Autographs` were not recognized as explicit autograph evidence. The matcher was corrected only for that observed case, while existing wrong-card, parallel, grading, and serial safeguards remained intact. The balanced 30-row corpus now clears the matcher-quality and breadth gates in CI.

This is an **identity-resolution milestone, not a valuation-readiness claim**. Public item pages marked `public_item_identity_only` cannot contribute to the price sanity subset. Only rows explicitly tagged `sold_identity_and_price_sanity` may do so, and even those remain weaker than authenticated eBay Product Research history.

## Current official eBay constraint
As of August 2026, eBay documents Marketplace Insights as Limited Release/restricted and not open to new users. eBay Product Research remains eBay's own historical sales-data surface and provides up to three years of sales data. Browse API provides live item/listing discovery but not general sold-history access.

## Production path
1. Treat the current balanced public corpus as empirical proof of entity-resolution behavior, not as authoritative valuation history.
2. Use Browse API for current supply once Production credentials are configured.
3. Use the bounded SoldComps adapter for zero-cost private-alpha evidence; never treat Best Offer asking prices as realized transactions.
4. Verify accepted observations against PSA or direct auction results before permitting evidence grade A.
5. Ingest a sanitized genuine Product Research export for authoritative historical-price and forward-valuation-error proof.
6. Run the existing Product Research receipt, corpus proof, and valuation gates without weakening thresholds.
7. If Marketplace Insights access becomes available, switch the sold provider with no downstream architecture changes.
8. Preserve every raw source record and comp-match decision for audit/calibration.

## Credential rule
The zero-cost sold path expects `SOLD_COMPS_API_KEY`. Official eBay supply access expects `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET`. Never commit secrets or share them in chat.
