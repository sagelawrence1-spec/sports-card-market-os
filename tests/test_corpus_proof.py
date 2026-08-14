from corpus_proof import ProofPolicy, build_corpus_proof_report, load_delimited_export


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
            "player": "Aaron Judge",
            "sport": "Baseball",
            "year": "2025",
            "card_number": "2",
        },
        {
            "card_id": "C",
            "player": "Stephen Curry",
            "sport": "Basketball",
            "year": "2025",
            "card_number": "3",
        },
        {
            "card_id": "D",
            "player": "Kevin Durant",
            "sport": "Basketball",
            "year": "2025",
            "card_number": "4",
        },
    ]


def raw_rows():
    rows = []
    for i, card in enumerate(candidates(), start=1):
        for j in range(2):
            rows.append({
                "Item ID": f"12345678{i}{j}",
                "Title": f"2025 {card['player']} #{card['card_number']}",
                "Sold Date": "2026-08-01",
                "Sold Price": "100",
                "Currency": "USD",
            })
    return rows


def labels():
    out = []
    mapping = ["A", "A", "B", "B", "C", "C", "D", "D"]
    for row, card in zip(raw_rows(), mapping):
        out.append({
            "evidence_id": row["Item ID"],
            "expected_status": "accepted",
            "expected_card_id": card,
        })
    return out


def policy():
    return ProofPolicy(
        target_cards=4,
        min_labeled_rows=8,
        min_label_coverage=0.90,
        min_positive_recall=0.80,
        max_single_card_share=0.30,
        max_sport_share=0.50,
    )


def test_balanced_clean_real_corpus_can_be_proof_ready():
    report = build_corpus_proof_report(raw_rows(), candidates(), labels(), policy=policy())
    assert report["proof_ready"] is True
    assert report["proof_version"] == "routing-proof.v6"
    assert report["routing"]["auto_accept_precision"] == 1.0
    assert report["routing"]["positive_recall"] == 1.0
    assert report["policy"]["min_positive_recall"] == 0.80
    assert report["policy"]["min_label_coverage"] == 0.90
    assert report["labels"]["coverage"] == 1.0
    assert report["labels"]["unlabeled_sanitized_rows"] == 0
    assert report["labels"]["distinct_labeled_cards"] == 4
    assert report["labels"]["prediction_source"] == "current_entity_matcher"


def test_orphan_label_fails_closed():
    label_rows = labels() + [{
        "evidence_id": "missing",
        "expected_status": "accepted",
        "expected_card_id": "A",
    }]
    report = build_corpus_proof_report(raw_rows(), candidates(), label_rows, policy=policy())
    assert report["proof_ready"] is False
    assert "labels_outside_sanitized_corpus" in report["blockers"]


def test_wrong_ground_truth_card_exposes_live_matcher_false_accept():
    label_rows = labels()
    label_rows[0] = {**label_rows[0], "expected_card_id": "B"}
    report = build_corpus_proof_report(raw_rows(), candidates(), label_rows, policy=policy())
    assert report["proof_ready"] is False
    assert report["routing"]["false_accepts"] == 1
    assert report["routing"]["wrong_card_accepts"] == 1


def test_caller_cannot_forge_predictions_in_label_file():
    label_rows = labels()
    label_rows[0] = {
        **label_rows[0],
        "predicted_status": "rejected",
        "predicted_card_id": "D",
    }
    report = build_corpus_proof_report(raw_rows(), candidates(), label_rows, policy=policy())
    assert report["proof_ready"] is True
    assert report["labels"]["caller_predictions_ignored"] == 1
    assert report["predictions"][label_rows[0]["evidence_id"]]["predicted_status"] == "accepted"
    assert report["predictions"][label_rows[0]["evidence_id"]]["predicted_card_id"] == "A"


def test_low_recall_cannot_pass_on_perfect_precision():
    rows = raw_rows()
    rows[0] = {**rows[0], "Title": "2025 baseball card #1"}
    rows[2] = {**rows[2], "Title": "2025 baseball card #2"}
    report = build_corpus_proof_report(
        rows,
        candidates(),
        labels(),
        policy=policy(),
    )
    assert report["routing"]["false_accepts"] == 0
    assert report["routing"]["auto_accept_precision"] == 1.0
    assert report["routing"]["positive_recall"] == 0.75
    assert report["proof_ready"] is False
    assert "positive_recall_below_floor" in report["blockers"]


def test_unlabeled_rows_cannot_be_hidden_from_proof():
    report = build_corpus_proof_report(
        raw_rows(),
        candidates(),
        labels()[:7],
        policy=ProofPolicy(
            target_cards=4,
            min_labeled_rows=7,
            min_label_coverage=0.90,
            min_positive_recall=0.80,
            max_single_card_share=0.40,
            max_sport_share=0.50,
        ),
    )
    assert report["labels"]["coverage"] == 0.875
    assert report["labels"]["unlabeled_sanitized_rows"] == 1
    assert report["proof_ready"] is False
    assert "label_coverage_below_floor" in report["blockers"]


def test_duplicate_labels_do_not_inflate_coverage_or_routing_sample():
    duplicate = labels()[:7] + [labels()[0], labels()[0], labels()[0]]
    report = build_corpus_proof_report(
        raw_rows(),
        candidates(),
        duplicate,
        policy=ProofPolicy(
            target_cards=4,
            min_labeled_rows=8,
            min_label_coverage=0.90,
            min_positive_recall=0.80,
            max_single_card_share=0.40,
            max_sport_share=0.50,
        ),
    )
    assert report["labels"]["provided"] == 10
    assert report["labels"]["scoped"] == 7
    assert report["labels"]["unique_scoped"] == 7
    assert report["labels"]["duplicate_rows_collapsed"] == 3
    assert report["routing"]["labeled_rows"] == 7
    assert report["labels"]["coverage"] == 0.875
    assert "label_coverage_below_floor" in report["blockers"]
    assert "routing:insufficient_labeled_rows" in report["blockers"]


def test_conflicting_duplicate_labels_fail_closed_and_are_excluded():
    label_rows = labels() + [{
        **labels()[0],
        "expected_card_id": "B",
    }]
    report = build_corpus_proof_report(
        raw_rows(),
        candidates(),
        label_rows,
        policy=ProofPolicy(
            target_cards=4,
            min_labeled_rows=7,
            min_label_coverage=0.80,
            min_positive_recall=0.80,
            max_single_card_share=0.40,
            max_sport_share=0.50,
        ),
    )
    assert report["labels"]["scoped"] == 7
    assert report["routing"]["labeled_rows"] == 7
    assert report["labels"]["conflicting_evidence_ids"] == [labels()[0]["evidence_id"]]
    assert report["proof_ready"] is False
    assert "conflicting_duplicate_labels" in report["blockers"]


def test_incomplete_card_coverage_fails_closed():
    report = build_corpus_proof_report(
        raw_rows(),
        candidates(),
        labels()[:6],
        policy=ProofPolicy(
            target_cards=4,
            min_labeled_rows=6,
            min_label_coverage=0.70,
            min_positive_recall=0.80,
            max_single_card_share=0.40,
            max_sport_share=0.50,
        ),
    )
    assert report["proof_ready"] is False
    assert "selected_card_coverage_incomplete" in report["blockers"]


def test_invalid_recall_floor_is_rejected():
    try:
        ProofPolicy(min_positive_recall=1.01)
    except ValueError as exc:
        assert "min_positive_recall" in str(exc)
    else:
        raise AssertionError("invalid recall floor should fail")


def test_invalid_label_coverage_floor_is_rejected():
    try:
        ProofPolicy(min_label_coverage=1.01)
    except ValueError as exc:
        assert "min_label_coverage" in str(exc)
    else:
        raise AssertionError("invalid label coverage floor should fail")


def test_load_delimited_export_handles_tsv(tmp_path):
    path = tmp_path / "export.tsv"
    tab = chr(9)
    path.write_text(
        tab.join(["Item ID", "Title", "Sold Date", "Sold Price", "Currency"])
        + "\n"
        + tab.join(["123456789", "2025 Shohei Ohtani #1", "2026-08-01", "100", "USD"])
        + "\n"
    )
    rows = load_delimited_export(path)
    assert rows[0]["Item ID"] == "123456789"
