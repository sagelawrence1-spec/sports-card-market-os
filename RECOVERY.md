# v0.7.4 recovery provenance

The original ChatGPT sandbox commit `c39d367` was reported as v0.7.4 but was never
persisted locally or pushed to GitHub. This repository reconstructs that release from:

- the surviving v0.4 source archive;
- the recorded v0.7.1-v0.7.4 release behavior and validation notes; and
- new regression tests for the recovered production-data invariants.

It does not claim byte-for-byte identity with the unavailable sandbox. The recovery
preserves the important invariants: strict card identity, USD/future-sale isolation,
outlier-resistant estimates, idempotent bulk import, manual review, evidence confidence,
and realized-outcome calibration gates.
