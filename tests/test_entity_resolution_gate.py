import pytest

from entity_resolution_gate import RegistryExpansionPolicy, assess_registry_expansion


def _evaluation(**overrides):
    metrics = {
        "rows": 12,
        "positive_labels": 6,
        "negative_labels": 6,
        "accepted": 6,
        "manual_review": 1,
        "true_accepts": 6,
        "false_accepts": 0,
        "missed_positives": 0,
        "precision": 1.0,
        "recall": 1.0,
        "false_accept_rate": 0.0,
        "review_rate": 0.0833,
    }
    metrics.update(overrides)
    return {
        "schema": "entity-resolution-eval.v1",
        "overall": metrics,
        "by_family": {"Topps::Chrome": metrics},
    }


def test_family_with_sufficient_clean_evidence_is_ready():
    result = assess_registry_expansion(_evaluation(), "Topps::Chrome")
    assert result["ready"] is True
    assert result["blockers"] == []


def test_observed_false_accept_blocks_expansion_even_with_high_precision():
    result = assess_registry_expansion(
        _evaluation(false_accepts=1, precision=0.99, false_accept_rate=0.01),
        "Topps::Chrome",
    )
    assert result["ready"] is False
    assert "observed_false_accepts" in result["blockers"]
    assert "false_accept_rate_above_ceiling" in result["blockers"]


def test_under_sampled_family_fails_closed_despite_clean_metrics():
    result = assess_registry_expansion(
        _evaluation(rows=4, positive_labels=2, negative_labels=2),
        "Topps::Chrome",
    )
    assert result["ready"] is False
    assert "insufficient_family_rows" in result["blockers"]
    assert "insufficient_positive_labels" in result["blockers"]
    assert "insufficient_negative_labels" in result["blockers"]


def test_missing_family_fails_closed():
    result = assess_registry_expansion(_evaluation(), "Bowman::Chrome")
    assert result["ready"] is False
    assert "family_not_measured" in result["blockers"]


def test_recall_and_review_burden_are_hard_gates():
    result = assess_registry_expansion(
        _evaluation(recall=0.79, review_rate=0.36),
        "Topps::Chrome",
    )
    assert "recall_below_floor" in result["blockers"]
    assert "review_rate_above_ceiling" in result["blockers"]


def test_policy_and_schema_validation_fail_closed():
    with pytest.raises(ValueError, match="min_family_rows"):
        RegistryExpansionPolicy(min_family_rows=0)
    with pytest.raises(ValueError, match="unsupported"):
        assess_registry_expansion({"schema": "old", "by_family": {}}, "Topps::Chrome")
