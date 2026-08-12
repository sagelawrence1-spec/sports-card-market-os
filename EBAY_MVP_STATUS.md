# eBay MVP Status — v0.4

## Implemented
- Official eBay Browse API adapter for live listings/supply.
- OAuth client-credentials token flow using environment variables; secrets are never stored in source.
- eBay Product Research structured-ingestion adapter for authoritative historical sales extracts.
- Marketplace Insights provider boundary, ready to replace the fallback if approved access exists.
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

## Current official eBay constraint
As of August 2026, eBay documents Marketplace Insights as Limited Release/restricted and not open to new users. eBay Product Research remains eBay's own historical sales-data surface and provides up to three years of sales data. Browse API provides live item/listing discovery but not general sold-history access.

## Production path
1. Use Browse API for current supply once Production credentials are configured.
2. Use eBay Product Research extracts as the authoritative sold-comp source initially.
3. If Marketplace Insights access becomes available, switch the sold provider with no downstream architecture changes.
4. Preserve every raw source record and comp-match decision for audit/calibration.

## Credential rule
Runtime expects `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET`. Never commit secrets into the repository or share them in chat.
