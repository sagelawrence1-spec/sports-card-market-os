# eBay MVP Status — v0.5

## Implemented
- Official eBay Browse API adapter for live listings/supply.
- OAuth client-credentials token flow using environment variables; secrets are never stored in source.
- eBay Product Research structured-ingestion adapter for authoritative historical sales extracts.
- Marketplace Insights provider boundary, ready to replace the fallback if approved access exists.
- Automatic SoldComps public-result adapter with grouped query rotation, strict
  Best Offer rejection, buyer-cost normalization, and evidence-grade ceiling.
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
- Leakage-safe empirical matcher evaluation now reports overall, family, and per-card metrics plus decision-reason histograms.
- Public-eBay corpus health gate separates matcher quality from corpus breadth and from Product Research price authority.

## Current measured bootstrap
The first 15-row genuine public SOLD bootstrap exposed a real matcher recall failure instead of manufacturing a pass. Observed-data fixes then lifted the current matcher above the bootstrap quality thresholds while retaining zero observed false accepts.

That is **not** a production-readiness claim. The corpus breadth gate now fails closed until there are at least 30 genuine rows with meaningful two-sided coverage per canonical card. The current fixture is still sparse: some cards lack enough positive or negative examples. Public SOLD pages remain identity-resolution evidence and a limited visible-price sanity subset, not a substitute for authenticated Product Research history.

## Current official eBay constraint
As of August 2026, eBay documents Marketplace Insights as Limited Release/restricted and not open to new users. eBay Product Research remains eBay's own historical sales-data surface and provides up to three years of sales data. Browse API provides live item/listing discovery but not general sold-history access.

## Production path
1. Expand the genuine public-eBay identity corpus until the breadth gate passes without weakening matcher thresholds.
2. Use Browse API for current supply once Production credentials are configured.
3. Use the bounded SoldComps adapter for zero-cost private-alpha evidence; never treat Best Offer asking prices as realized transactions.
4. Verify accepted observations against PSA or direct auction results before permitting evidence grade A.
5. Ingest a sanitized genuine Product Research export for authoritative historical-price and forward-valuation-error proof.
6. If Marketplace Insights access becomes available, switch the sold provider with no downstream architecture changes.
7. Preserve every raw source record and comp-match decision for audit/calibration.

## Credential rule
The zero-cost sold path expects `SOLD_COMPS_API_KEY`. Official eBay supply access expects `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET`. Never commit secrets or share them in chat.
