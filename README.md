# Sports Card Market OS

Sports-card market intelligence built around auditable sold evidence, strict card
identity, robust valuation, and measurable forward outcomes.

Current maturity: **private engine alpha**. The v0.7.5 code is a reconstructed
engine baseline with an experimental Opportunity Engine MVP, not a finished
application. See [RECOVERY.md](RECOVERY.md). Release progression and evidence gates
are defined in [ROADMAP.md](ROADMAP.md).

The product direction is a continuously operating market-intelligence system:
market evidence → card identity → valuation → opportunity → capital decision →
realized outcome → calibration. The current interface demonstrates that workflow,
but its visible market state is explicitly illustrative until verified data
ingestion and forward validation are live.

## Priorities

1. Continuously ingest verified sold evidence and reject corrupt comps.
2. Resolve every observation through a canonical card registry and hierarchy.
3. Persist market history, evidence grades, deltas, and material alerts.
4. Journal recommendations before outcomes and measure forward performance.
5. Allocate capital only when evidence and calibration gates pass.

## Opportunity Engine MVP

`opportunity_engine.py` adds a separate player-level hypothesis layer for situations
where the real-world story may be moving before the card market has fully repriced.
It is deliberately distinct from the existing card-level quant engine.

The MVP supports three thesis types (`EDGE`, `CATALYST`, `QUANT`) and an explicit
opportunity lifecycle:

`PRE_CATALYST → ENTRY → ACCELERATION → CONSENSUS`

A thesis can also move to `BROKEN`. Lifecycle stages are monotonic so later evidence
cannot silently rewrite an earlier call.

The key design constraint is that **evidence confidence and edge conviction are not
the same score**. A weak-signal idea can have low evidence maturity but still be
worth journaling when hobby lag, narrative potential, collectibility, and upside
asymmetry are unusually strong. Every create/update action is persisted to an
append-only thesis ledger before the outcome is known.

### Spark

The first user-facing entry point is the Spark CLI. It turns a human observation
into a persistent thesis instead of a disposable chat response:

```bash
python opportunity_cli.py --db opportunity.sqlite spark "Munetaka Murakami" \
  --sport MLB \
  --signal-type SIGNING \
  --observation "Major-league signing creates a concrete entry catalyst before breakout confirmation."
```

Inspect the active radar:

```bash
python opportunity_cli.py --db opportunity.sqlite radar
```

Inspect one thesis, including its signal history and timestamped ledger:

```bash
python opportunity_cli.py --db opportunity.sqlite show <thesis_id>
```

`opportunity_contract.py` emits the versioned `opportunity-radar.v1` payload for a
future Radar surface. The first acceptance tests encode the two canonical product
requirements discussed during design: a Murakami-style signing should be able to
surface an ENTRY opportunity before breakout confirmation, and a Westbrook-style
retirement-risk setup should be able to surface before an actual retirement
announcement.

This experimental subsystem does **not** bypass the repository's evidence gates.
It exists to journal and test pre-consensus hypotheses so the system can prove or
disprove whether early calls have measurable value rather than relying on hindsight.

## Engine-to-interface contract

`market_contract.py` emits the versioned `market-scan.v1` payload consumed by the
Market Scan and Card Intelligence surfaces. The interface renders three source
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
monitored universe into player/year/grade searches, rotates those groups through a
bounded daily request budget, and excludes Best Offers because eBay does not expose
the negotiated price. Missing shipping, non-USD transactions, malformed totals,
ambiguous identity, lots, and reprints are also rejected. This source is capped at
evidence grade B until an independent realized-sale source agrees.

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
selected provider's secret and variables are configured. Its generated contract is
retained as a run artifact for inspection; automated product publication is
intentionally deferred until the confirmed source is activated.

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
