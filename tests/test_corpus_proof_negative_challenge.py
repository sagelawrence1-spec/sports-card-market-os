from corpus_proof import ProofPolicy, build_corpus_proof_report


def candidates():
    return [
        {
            "card_id": "A",
            "player": "Shohei Ohtani",
            "sport": "Baseball",
            "year": "2025",
            "card_number": "1",
        },
        {
            "card_id": "B",
            "player": "Stephen Curry",
            "sport": "Basketball",
            "year": "2025",
            "card_number": "2",
        },
    ]


def raw_rows():
    rows = []
    for i in range(4):
        rows.append({
            "Item ID": f"A{i}",
            "Title": "2025 Shohei Ohtani #1",
            "Sold Date": "2026-08-01",
            "Sold Price": "100",
            "Currency": "USD",
            "Shipping": "$0.00",
        })
    for i in range(4):
        rows.append({
            "Item ID": f"B{i}",
            "Title": "2025 Stephen Curry #2",
            "Sold Date": "2026-08-01",
            "Sold Price": "100",
            "Currency": "USD",
            "Shipping": "$0.00",
        })
    return rows


def labels(negative_count=0):
    out = []
    ids = [f"A{i}" for i in range(4)] + [f"B{i}" for i in range(4)]
    cards = ["A"] * 4 + ["B"] * 4
    for index, (evidence_id, card_id) in enumerate(zip(ids, cards)):
        if index < negative_count:
            out.append({
                "evidence_id": evidence_id,
                "expected_status": "rejected",
            })
        else:
            out.append({
                "evidence_id": evidence_id,
                "expected_status": "accepted",
                "expected_card_id": card_id,
            })
    return out


def policy():
    return ProofPolicy(
        target_cards=2,
        min_labeled_rows=8,
        min_label_coverage=1.0,
        min_positive_recall=0.0,
        min_negative_label_share=0.25,
        max_review_rate=1.0,
        max_single_card_share=1.0,
        max_sport_share=0.50,
    )


def test_all_positive_corpus_cannot_prove_false_accept_safety():
    report = build_corpus_proof_report(
        raw_rows(), candidates(), labels(), policy=policy()
    )

    assert report["labels"]["negative_rows"] == 0
    assert report["labels"]["negative_share"] == 0.0
    assert report["proof_ready"] is False
    assert "negative_label_share_below_floor" in report["blockers"]


def test_negative_challenge_share_is_measured_against_floor():
    report = build_corpus_proof_report(
        raw_rows(), candidates(), labels(negative_count=2), policy=policy()
    )

    assert report["labels"]["negative_rows"] == 2
    assert report["labels"]["negative_share"] == 0.25
    assert "negative_label_share_below_floor" not in report["blockers"]


def test_invalid_negative_label_share_floor_is_rejected():
    try:
        ProofPolicy(min_negative_label_share=1.01)
    except ValueError as exc:
        assert "min_negative_label_share" in str(exc)
    else:
        raise AssertionError("invalid negative label share floor should fail")
