# Tested v0.7 baseline

Source snapshot: local v0.7.4 release verified before GitHub initialization.

- Local artifact SHA-256: `b489c9303a0895ad81dd10aa19e3618837a8017fc5de53fe29878165e86a980b`
- Verification: `pytest -q` -> `16 passed`
- Compile gate: `python -m compileall -q .` -> clean
- Baseline emphasis: eBay Product Research ingestion, precision entity matching, comp adjudication, persistent evidence/history, review resolution, readiness, walk-forward/outcome grading, API/PWA path.

## Source-of-truth transition

GitHub is now the authoritative project tracker and development surface. New work lands on `feature/*` branches, targets `develop` by pull request, and reaches `main` only after CI passes and the release is considered stable.

The remaining baseline source files are being migrated from the verified local snapshot into the repository without changing behavior during migration. Feature work should not bypass this gate.
