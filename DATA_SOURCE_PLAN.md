# Data Source Plan — v0.3

## 1. Active listing/supply data
Use eBay Browse API for active listings and listing snapshots where production access is approved. Store raw query, item ID, title, price, condition, seller, listing type, and timestamp before normalization.

## 2. Sold-history data
Do not architect around eBay Marketplace Insights availability. Treat sold history as a pluggable provider because Marketplace Insights is restricted. Initial supported paths: licensed provider/API, auction-house exports, PSA Auction Prices exports where permitted, and normalized manual/CSV imports.

## 3. PSA populations
PSA's Population Report is updated daily and is the target population source. PSA's currently documented public API explicitly lists cert-verification methods, so population ingestion remains a separate adapter boundary until an authorized population method is available to the project.

## 4. Provenance rule
Never mix a derived comp with a raw transaction. Every record should retain provider/source, source item ID, ingestion timestamp, and normalization version.

## 5. Next adapter priorities
1. eBay active listings
2. PSA population snapshots
3. sold-history provider
4. Goldin / Fanatics Collect / auction-house result imports
5. athlete-stat/event feeds
6. search/social demand proxies
