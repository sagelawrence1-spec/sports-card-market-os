import pytest

from routing_audit import RoutingLabel, audit_routing, labels_from_rows


def test_clean_sample_stays_blocked_until_minimum_size():
    labels = [
        RoutingLabel(str(i), "accepted", "accepted", "card-a", "card-a")
        for i in range(10)
    ]
    report = audit_routing(labels, min_labeled_rows=50)

    assert report["auto_accept_precision"] == 1.0
    assert report["production_ready"] is False
    assert report["blockers"] == ["insufficient_labeled_rows"]


def test_false_accept_fails_closed_even_with_large_sample():
    labels = [
        RoutingLabel(str(i), "accepted", "accepted", "card-a", "card-a")
        for i in range(99)
    ]
    labels.append(RoutingLabel("bad", "accepted", "rejected", "card-a", None))

    report = audit_routing(labels, min_labeled_rows=50)

    assert report["false_accepts"] == 1
    assert report["auto_accept_precision"] == pytest.approx(0.99)
    assert report["production_ready"] is False
    assert "observed_false_accepts" in report["blockers"]


def test_wrong_card_auto_accept_counts_as_false_accept():
    labels = [
        RoutingLabel("1", "accepted", "accepted", "wrong-card", "right-card")
    ]
    report = audit_routing(labels, min_labeled_rows=1)

    assert report["true_accepts"] == 0
    assert report["false_accepts"] == 1
    assert report["wrong_card_accepts"] == 1
    assert report["production_ready"] is False


def test_review_capture_and_recall_are_reported():
    labels = [
        RoutingLabel("1", "accepted", "accepted", "card-a", "card-a"),
        RoutingLabel("2", "review", "accepted", "card-a", "card-a"),
        RoutingLabel("3", "review", "rejected", "card-a", None),
        RoutingLabel("4", "rejected", "rejected", "card-a", None),
    ]
    report = audit_routing(labels, min_labeled_rows=4)

    assert report["positive_recall"] == 0.5
    assert report["review_rate"] == 0.5
    assert report["review_capture"] == 2


def test_labels_from_rows_validates_statuses():
    rows = [{
        "evidence_id": "e1",
        "predicted_status": "accepted",
        "expected_status": "accepted",
        "predicted_card_id": "card-a",
        "expected_card_id": "card-a",
    }]
    labels = labels_from_rows(rows)
    assert labels[0].evidence_id == "e1"

    with pytest.raises(ValueError):
        labels_from_rows([{
            "evidence_id": "e2",
            "predicted_status": "maybe",
            "expected_status": "accepted",
        }])
