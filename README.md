# Sports Card Market OS

Sports-card market intelligence built around auditable sold evidence, strict card
identity, robust valuation, and measurable forward outcomes.

Current maturity: **public engine alpha**. The v0.7.4 code is a reconstructed
engine baseline, not a finished application. See [RECOVERY.md](RECOVERY.md).
Release progression and evidence gates are defined in [ROADMAP.md](ROADMAP.md).

Use the public alpha at
[sagelawrence1-spec.github.io/sports-card-market-os](https://sagelawrence1-spec.github.io/sports-card-market-os/).
It is an evidence-first operating view, not a promise of actionable pricing:
when the data has not cleared the trust gates, the product deliberately says
**Not enough evidence** and recommends no action.

The product direction is a continuously operating market-intelligence system:
market evidence → card identity → valuation → opportunity → capital decision →
realized outcome → calibration. The current interface publishes scheduled public
sold-result evidence with explicit source limitations. Capital guidance remains
locked until verified data quality and forward calibration are proven.

## Priorities

1. Continuously ingest verified sold evidence and reject corrupt comps.
2. Resolve every observation through a canonical card registry and hierarchy.
3. Persist market history, evidence grades, deltas, and material alerts.
4. Journal recommendations before outcomes and measure forward performance.
5. Allocate capital only when evidence and calibration gates pass.

## Engine-to-interface contract

`market_contract.py` emits the versioned `market-scan.v1` payload consumed by the
Today, Market, Card Intelligence, Review Queue, and Data Health surfaces. The interface renders three source
states without hiding provenance: illustrative alpha, scheduled evidence, and a
blocked sold-data state. A valuation is displayed only after the accepted sold
sample clears its evidence gate; otherwise the product says **Not enough
evidence**.

`market_runner.py` drives the automatic loop: it loads the monitored canonical
registry, queries the configured sold and active-listing providers, resolves each
observation, persists the evidence and market history, and atomically emits the
product contract. Capital actions remain withheld until both evidence and forward
calibration gates pass. Internal `WATCH` and `AVOID` states cannot be promoted
into public BUY / ACCUMULATE / HOLD / TRIM / SELL actions.

## Automatic evidence run

The sold-data boundary supports three replaceable providers. The zero-cost
private-alpha path uses SoldComps' public eBay sold-result API. It groups the
monitored universe into player/year/grade searches, rotates those groups through
a bounded daily request budget, and excludes Best Offers because eBay does not
expose the negotiated price. Missing shipping, non-USD transactions, malformed
totals, ambiguous identity, lots, and reprints are also rejected. This source is
capped at evidence grade B until an independent realized-sale source agrees.

The Card API paid feed and official eBay Marketplace Insights remain optional
upgrades behind the same provider boundary.

Configure a free SoldComps key using `.env.example`, then run:

```bash
python market_runner.py
```

Without a configured sold source the runner refuses to replace the product payload.
For local inspection of the explicit blocked state only:

```bash
python market_runner.py --allow-blocked --database /tmp/market-os.sqlite --output /tmp/market-scan.json
```

`.github/workflows/market-scan.yml` provides the gated daily/dispatch job. It is
disabled until the repository variable `MARKET_SCAN_ENABLED=true` and the
selected provider's secret and variables are configured. Each successful run
restores the bounded evidence database, creates a compact public history, computes
material changes against the prior snapshot, commits only the two public data
files, and triggers the normal tested Pages deployment. Generated contracts are
also retained as short-lived run artifacts for inspection.

The public Review Queue is deliberately read-only: it shows held listing rows,
their proposed canonical cards, and the reason each match is excluded from
valuation. Registry-changing decisions remain operator-only so anonymous visitors
cannot approve corrupt evidence.

SoldComps is treated as public-result evidence rather than authoritative eBay
transaction data. The API key remains a user-owned secret and is never committed
or exposed to the browser. Best Offer rows remain in the audit store as rejected
evidence and can never affect valuation.

## Validate

```bash
python -m pip install -e '.[dev]'
pytest
python grader.py /path/to/raw_test_data /path/to/synthetic_answer_key.csv
```

The large synthetic fixture is intentionally kept outside Git. Synthetic classification
validates engineered regimes; it is not evidence of live-market edge.

## Open source

Sports Card Market OS is released under the [MIT License](LICENSE). Contributions
are welcome through short-lived branches and focused pull requests. Never commit
provider credentials, personal portfolio data, or proprietary exports.
