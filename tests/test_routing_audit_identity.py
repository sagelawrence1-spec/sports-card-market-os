from routing_audit import RoutingLabel, audit_routing


def test_accepted_label_without_expected_card_id_fails_closed():
    report = audit_routing(
        [RoutingLabel("e1", "accepted", "accepted", "card-a", None)],
        min_labeled_rows=1,
    )

    assert report["accepted_labels_missing_card_id"] == 1
    assert report["true_accepts"] == 0
    assert report["false_accepts"] == 1
    assert report["wrong_card_accepts"] == 1
    assert report["auto_accept_precision"] == 0.0
    assert report["production_ready"] is False
    assert "accepted_labels_missing_card_id" in report["blockers"]
    assert "observed_false_accepts" in report["blockers"]


def test_negative_label_without_expected_card_id_remains_valid():
    report = audit_routing(
        [RoutingLabel("e1", "rejected", "rejected", "card-a", None)],
        min_labeled_rows=1,
    )

    assert report["accepted_labels_missing_card_id"] == 0
    assert report["false_accepts"] == 0
    assert report["production_ready"] is True
