# Product Research Fast Lane

This is the shortest path to the first genuine Sports Card Market OS empirical corpus.

## Goal

Collect one complete, untouched eBay Product Research result set for each of the six canonical live Radar cards. Do not hand-filter rows. The OS owns acceptance/rejection and review accounting.

## Collection rules

- Source: eBay Product Research only.
- Use the exact query below.
- Use the full requested sold-date window where the Product Research UI permits it.
- Preserve actual sold price, shipping, sold date, item number, quantity, selling format, title, URL, and currency provenance when present.
- Export/save the complete result set; do not delete obvious bad comps.
- Keep the exact filename below.
- One file per card.

## Six-card corpus

| # | Player | Exact query | Sold window | Required filename |
|---|---|---|---|---|
| 1 | Elian Pena | `2025 Elian Pena Bowman Chrome CPA-EP autograph` | 2026-07-19 through 2026-08-20 | `01-elian-pena-2025-bowman-chrome-prospect-autograph-cpa-ep-elian-pena.csv` |
| 2 | George Wolkow | `2024 George Wolkow Bowman Chrome CPA-GWO autograph` | 2026-07-19 through 2026-08-20 | `02-george-wolkow-2024-bowman-chrome-prospect-autograph-cpa-gwo-george-wolkow.csv` |
| 3 | Kaytron Allen | `2025 Kaytron Allen Bowman Chrome University BCA-KA autograph` | 2026-07-16 through 2026-08-20 | `03-kaytron-allen-2025-bowman-chrome-university-prospect-autograph-bca-ka-kaytron-allen.csv` |
| 4 | Franklin Arias | `2025 Franklin Arias Bowman Chrome CPA-FA autograph` | 2026-07-15 through 2026-08-20 | `04-franklin-arias-2025-bowman-chrome-prospect-autograph-cpa-fa-franklin-arias.csv` |
| 5 | Bo Davidson | `2025 Bo Davidson Bowman Chrome CPA-BD autograph` | 2026-07-18 through 2026-08-20 | `05-bo-davidson-2025-bowman-chrome-prospect-autograph-cpa-bd-bo-davidson.csv` |
| 6 | Caleb Bonemer | `2024 Caleb Bonemer Bowman Draft Chrome CPA-CBO autograph` | 2026-07-19 through 2026-08-20 | `06-caleb-bonemer-2024-bowman-draft-chrome-prospect-autograph-cpa-cbo-caleb-bonemer.csv` |

## Definition of done

The corpus blocker is removed when all six raw files exist unchanged and the existing authoritative research/corpus pipeline produces measured:

1. accepted-comp precision / false accepts,
2. matcher recall / false rejects,
3. manual review burden,
4. valuation error against the adjudicated card-level reference set,
5. raw-file SHA-256 receipts so the proof is reproducible.

## Do not substitute

Public completed-listing search is useful for exploration but is not a substitute for this corpus. Product Research exposes more complete transaction data, including actual accepted Best Offer prices, and is the authoritative source for this proof tranche.
