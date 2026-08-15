from corpus_proof import ProofPolicy, build_corpus_proof_report


def _candidates():
    return [
        {"card_id": "A", "player": "Shohei Ohtani", "sport": "Baseball", "year": "2025", "card_number": "1"},
        {"card_id": "B", "player": "Aaron Judge", "sport": "Baseball", "year": "2025", "card_number": "2"},
        {"card_id": "C", "player": "Stephen Curry", "sport": "Basketball", "year": "2025", "card_number": "3"},
        {"card_id": "D", "player": "Kevin Durant", "sport": "Basketball", "year": "2025", "card_number": "4"},
    ]


def _valid_rows():
    rows = []
    for i, card in enumerate(_candidates(), start=1):
        for j in range(2):
            rows.append({
                "Item ID": f"12345678{i}{j}",
                "Title": f"2025 {card['player']} #{card['card_number']}",
                "Sold Date": "2026-08-01",
                "Sold Price": "100",
                "Currency": "USD",
            })
    return rows


def _labels():
    mapping = ["A", "A", "B", "B", "C", "C", "D", "D"]
    return [
        {
            "evidence_id": row["Item ID"],
            "expected_status": "accepted",
            "expected_card_id": card_id,
        }
        for row, card_id in zip(_valid_rows(), mapping)
    ]


def _policy(**overrides):
    values = dict(
        target_cards=4,
        min_labeled_rows=8,
        min_label_coverage=0.90,
        min_intake_retention=0.90,
        min_positive_recall=0.80,
        max_single_card_share=0.30,
        max_sport_share=0.50,
    )
    values.update(overrides)
    return ProofPolicy(**values)


def test_rejected_rows_cannot_disappear_from_proof_denominator():
    rows = _valid_rows() + [
        {
            "Item ID": "999999991",
            "Title": "broken price row",
            "Sold Date": "2026-08-01",
            "Sold Price": "$100 - $150",
            "Currency": "USD",
        },
        {
            "Item ID": "999999992",
            "Title": "non usd row",
            "Sold Date": "2026-08-01",
            "Sold Price": "100",
            "Currency": "EUR",
        },
    ]
    report = build_corpus_proof_report(rows, _candidates(), _labels(), policy=_policy())

    assert report["labels"]["coverage"] == 1.0
    assert report["intake"]["accepted_rows"] == 8
    assert report["intake"]["rejected_rows"] == 2
    assert report["intake"]["retention"] == 0.8
    assert report["proof_ready"] is False
    assert "intake_retention_below_floor" in report["blockers"]


def test_duplicate_rows_do_not_reduce_intake_retention():
    rows = _valid_rows() + [_valid_rows()[0]]
    report = build_corpus_proof_report(rows, _candidates(), _labels(), policy=_policy())

    assert report["intake"]["duplicates"] == 1
    assert report["intake"]["retention"] == 1.0
    assert "intake_retention_below_floor" not in report["blockers"]


def test_invalid_intake_retention_floor_is_rejected():
    try:
        ProofPolicy(min_intake_retention=1.01)
    except ValueError as exc:
        assert "min_intake_retention" in str(exc)
    else:
        raise AssertionError("invalid intake retention floor should fail")
