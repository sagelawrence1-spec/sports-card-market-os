# Development workflow

`main` is the only long-lived branch and the source of truth.

1. Create a short-lived `agent/<focused-scope>` branch from `main`.
2. Keep one coherent product increment per pull request.
3. Open the pull request against `main` as a draft.
4. Require both engine and alpha-web CI jobs to pass.
5. Mark ready, squash-merge, and delete the feature branch.

Do not target `develop`; it is retained only as historical branch state until it
can be removed safely. Avoid duplicate roadmap issues: extend #1–#5 instead.
