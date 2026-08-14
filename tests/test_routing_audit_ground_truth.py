from routing_audit import RoutingLabel, audit_routing


def test_review_ground_truth_cannot_make_routing_audit_production_ready():
    labels = [
        RoutingLabel(
            evidence_id="ambiguous-1",
            predicted_status="review",
            expected_status="review",
        )
    ]

    report = audit_routing(labels, min_labeled_rows=1)

    assert report["non_definitive_ground_truth"] == 1
    assert report["production_ready"] is False
    assert "non_definitive_ground_truth" in report["blockers"]


def test_definitive_negative_ground_truth_may_omit_card_identity():
    labels = [
        RoutingLabel(
            evidence_id="irrelevant-1",
            predicted_status="rejected",
            expected_status="rejected",
        )
    ]

    report = audit_routing(labels, min_labeled_rows=1)

    assert report["non_definitive_ground_truth"] == 0
    assert report["accepted_labels_missing_card_id"] == 0
    assert report["production_ready"] is True
