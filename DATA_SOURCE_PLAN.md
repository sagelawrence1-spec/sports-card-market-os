# Data Source Plan — v0.3

## 1. Active listing/supply data
Use eBay Browse API for active listings and listing snapshots where production access is approved. Store raw query, item ID, title, price, condition, seller, listing type, and timestamp before normalization.

## 2. Sold-history data
Do not architect around eBay Marketplace Insights availability. Treat sold history as a pluggable provider because Marketplace Insights is restricted. The private-alpha path uses bounded SoldComps public-result queries with Best Offers excluded and a B-grade ceiling. Paid licensed feeds, auction-house results, PSA Auction Prices where permitted, and normalized manual imports remain independent verification paths.

## 3. PSA populations
PSA's Population Report is updated daily and is the target population source. PSA's currently documented public API explicitly lists cert-verification methods, so population ingestion remains a separate adapter boundary until an authorized population method is available to the project.

## 4. Provenance rule
Never mix a derived comp with a raw transaction. Every record should retain provider/source, source item ID, ingestion timestamp, and normalization version.

## 5. Next adapter priorities
1. Independent verification for SoldComps-accepted observations
2. eBay active listings
3. PSA population snapshots
4. Goldin / Fanatics Collect / auction-house result imports
5. athlete-stat/event feeds
6. search/social demand proxies
