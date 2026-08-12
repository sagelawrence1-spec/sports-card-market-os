# Development workflow

1. `main` is stable/release state.
2. `develop` is the integration branch.
3. Create focused `feature/<scope>` branches from `develop`.
4. Pull requests target `develop`; keep one logical change per PR.
5. CI compile + tests must pass before merge.
6. Do not weaken precision, leakage, currency, duplicate, or review gates to make tests pass.
7. Real-data correctness outranks UI polish.
8. Promote `develop` to `main` only as an intentional tested release.
