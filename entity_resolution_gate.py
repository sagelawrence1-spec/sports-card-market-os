from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class RegistryExpansionPolicy:
    """Evidence floors required before widening a canonical card family."""

    min_family_rows: int = 10
    min_positive_labels: int = 3
    min_negative_labels: int = 3
    min_precision: float = 0.99
    min_recall: float = 0.80
    max_false_accept_rate: float = 0.0
    max_review_rate: float = 0.35

    def __post_init__(self) -> None:
        if self.min_family_rows < 1:
            raise ValueError("min_family_rows must be positive")
        if self.min_positive_labels < 1 or self.min_negative_labels < 1:
            raise ValueError("label class floors must be positive")
        for name in ("min_precision", "min_recall", "max_false_accept_rate", "max_review_rate"):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")


def assess_registry_expansion(
    evaluation: Mapping[str, Any],
    family: str,
    *,
    policy: RegistryExpansionPolicy | None = None,
) -> dict[str, Any]:
    """Fail closed unless one card family has enough leakage-safe evidence.

    The input is the read-only report produced by ``evaluate_entity_resolution``.
    This gate never tunes matcher behavior; it only decides whether registry breadth
    is supported by the measured corpus.
    """

    policy = policy or RegistryExpansionPolicy()
    if evaluation.get("schema") != "entity-resolution-eval.v1":
        raise ValueError("unsupported entity-resolution evaluation schema")

    metrics = (evaluation.get("by_family") or {}).get(family)
    blockers: list[str] = []
    if metrics is None:
        blockers.append("family_not_measured")
        metrics = {}

    rows = int(metrics.get("rows") or 0)
    positives = int(metrics.get("positive_labels") or 0)
    negatives = int(metrics.get("negative_labels") or 0)
    false_accepts = int(metrics.get("false_accepts") or 0)
    precision = metrics.get("precision")
    recall = metrics.get("recall")
    false_accept_rate = metrics.get("false_accept_rate")
    review_rate = metrics.get("review_rate")

    if rows < policy.min_family_rows:
        blockers.append("insufficient_family_rows")
    if positives < policy.min_positive_labels:
        blockers.append("insufficient_positive_labels")
    if negatives < policy.min_negative_labels:
        blockers.append("insufficient_negative_labels")
    if false_accepts > 0:
        blockers.append("observed_false_accepts")
    if precision is None or precision < policy.min_precision:
        blockers.append("precision_below_floor")
    if recall is None or recall < policy.min_recall:
        blockers.append("recall_below_floor")
    if false_accept_rate is None or false_accept_rate > policy.max_false_accept_rate:
        blockers.append("false_accept_rate_above_ceiling")
    if review_rate is None or review_rate > policy.max_review_rate:
        blockers.append("review_rate_above_ceiling")

    return {
        "schema": "registry-expansion-gate.v1",
        "family": family,
        "ready": not blockers,
        "blockers": blockers,
        "metrics": dict(metrics),
        "policy": {
            "min_family_rows": policy.min_family_rows,
            "min_positive_labels": policy.min_positive_labels,
            "min_negative_labels": policy.min_negative_labels,
            "min_precision": policy.min_precision,
            "min_recall": policy.min_recall,
            "max_false_accept_rate": policy.max_false_accept_rate,
            "max_review_rate": policy.max_review_rate,
        },
    }
