# Sports Card Market OS

Sports-card market intelligence built around auditable sold evidence, strict card
identity, robust valuation, and measurable forward outcomes.

Current release: **v0.7.4 (reconstructed baseline)**. See [RECOVERY.md](RECOVERY.md).

## Priorities

1. Correct eBay Product Research ingestion and card routing.
2. Reconstruct fair value without future leakage or currency contamination.
3. Measure calibration against actual subsequent accepted sales.
4. Expand product surfaces only after the data proves useful.

## Validate

```bash
python -m pip install -e '.[dev]'
pytest
python grader.py /path/to/raw_test_data /path/to/synthetic_answer_key.csv
```

The large synthetic fixture is intentionally kept outside Git. Synthetic classification
validates engineered regimes; it is not evidence of live-market edge.
