from dataclasses import dataclass

import pytest

from entity_resolution_metrics import evaluate_entity_resolution


@dataclass
class _Decision:
    accepted: bool
    reason: str


class _Matcher:
    def match(self, asset, title):
        if "ACCEPT" in title:
            return _Decision(True, "accepted")
        if "REVIEW" in title:
            return _Decision(False, "manual_review")
        return _Decision(False, "wrong_parallel")


def _row(set_name, title, expected_match):
    return {
        "asset": {"manufacturer": "Topps", "set_name": set_name},
        "title": title,
        "expected_match": expected_match,
    }


def test_reports_precision_recall_false_accepts_and_review_burden():
    result = evaluate_entity_resolution(
        [
            _row("Chrome", "ACCEPT positive", True),
            _row("Chrome", "REVIEW positive", True),
            _row("Chrome", "ACCEPT negative", False),
            _row("Chrome", "REJECT negative", False),
        ],
        matcher=_Matcher(),
    )

    overall = result["overall"]
    assert result["schema"] == "entity-resolution-eval.v1"
    assert overall["rows"] == 4
    assert overall["true_accepts"] == 1
    assert overall["false_accepts"] == 1
    assert overall["missed_positives"] == 1
    assert overall["manual_review"] == 1
    assert overall["precision"] == 0.5
    assert overall["recall"] == 0.5
    assert overall["false_accept_rate"] == 0.5
    assert overall["review_rate"] == 0.25


def test_reports_metrics_by_card_family():
    result = evaluate_entity_resolution(
        [
            _row("Chrome", "ACCEPT positive", True),
            _row("Chrome", "REVIEW positive", True),
            _row("Bowman Chrome", "ACCEPT negative", False),
        ],
        matcher=_Matcher(),
    )

    chrome = result["by_family"]["Topps::Chrome"]
    bowman = result["by_family"]["Topps::Bowman Chrome"]
    assert chrome["recall"] == 0.5
    assert chrome["review_rate"] == 0.5
    assert bowman["false_accept_rate"] == 1.0
    assert bowman["precision"] == 0.0


def test_zero_denominators_are_reported_as_none_not_fake_perfect_scores():
    result = evaluate_entity_resolution(
        [_row("Chrome", "REJECT negative", False)],
        matcher=_Matcher(),
    )
    overall = result["overall"]
    assert overall["precision"] is None
    assert overall["recall"] is None
    assert overall["false_accept_rate"] == 0.0


def test_rejects_non_definitive_or_malformed_labels():
    with pytest.raises(ValueError, match="expected_match must be boolean"):
        evaluate_entity_resolution(
            [{"asset": {}, "title": "x", "expected_match": "review"}],
            matcher=_Matcher(),
        )

    with pytest.raises(ValueError, match="non-empty title"):
        evaluate_entity_resolution(
            [{"asset": {}, "title": "", "expected_match": True}],
            matcher=_Matcher(),
        )
