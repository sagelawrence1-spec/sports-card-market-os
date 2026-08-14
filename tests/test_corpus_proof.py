from corpus_proof import ProofPolicy, build_corpus_proof_report, load_delimited_export


def candidates():
    return [
        {"card_id": "A", "player": "A", "sport": "Baseball"},
        {"card_id": "B", "player": "B", "sport": "Baseball"},
        {"card_id": "C", "player": "C", "sport": "Basketball"},
        {"card_id": "D", "player": "D", "sport": "Basketball"},
    ]


def raw_rows():
    rows = []
    for i, card in enumerate(["A", "B", "C", "D"], start=1):
        for j in range(2):
            rows.append({
                "Item ID": f"12345678{i}{j}",
                "Title": f"{card} card",
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
            "predicted_status": "accepted",
            "expected_status": "accepted",
            "predicted_card_id": card,
            "expected_card_id": card,
        })
    return out


def policy():
    return ProofPolicy(
        target_cards=4,
        min_labeled_rows=8,
        max_single_card_share=0.30,
        max_sport_share=0.50,
    )


def test_balanced_clean_real_corpus_can_be_proof_ready():
    report = build_corpus_proof_report(raw_rows(), candidates(), labels(), policy=policy())
    assert report["proof_ready"] is True
    assert report["routing"]["auto_accept_precision"] == 1.0
    assert report["labels"]["distinct_labeled_cards"] == 4


def test_orphan_label_fails_closed():
    label_rows = labels() + [{
        "evidence_id": "missing",
        "predicted_status": "accepted",
        "expected_status": "accepted",
        "predicted_card_id": "A",
        "expected_card_id": "A",
    }]
    report = build_corpus_proof_report(raw_rows(), candidates(), label_rows, policy=policy())
    assert report["proof_ready"] is False
    assert "labels_outside_sanitized_corpus" in report["blockers"]


def test_wrong_card_accept_fails_closed():
    label_rows = labels()
    label_rows[0] = {**label_rows[0], "predicted_card_id": "B"}
    report = build_corpus_proof_report(raw_rows(), candidates(), label_rows, policy=policy())
    assert report["proof_ready"] is False
    assert report["routing"]["false_accepts"] == 1


def test_incomplete_card_coverage_fails_closed():
    report = build_corpus_proof_report(
        raw_rows(),
        candidates(),
        labels()[:6],
        policy=ProofPolicy(
            target_cards=4,
            min_labeled_rows=6,
            max_single_card_share=0.40,
            max_sport_share=0.50,
        ),
    )
    assert report["proof_ready"] is False
    assert "selected_card_coverage_incomplete" in report["blockers"]


def test_load_delimited_export_handles_tsv(tmp_path):
    path = tmp_path / "export.tsv"
    tab = chr(9)
    path.write_text(
        tab.join(["Item ID", "Title", "Sold Date", "Sold Price", "Currency"])
        + "\n"
        + tab.join(["123456789", "A card", "2026-08-01", "100", "USD"])
        + "\n"
    )
    rows = load_delimited_export(path)
    assert rows[0]["Item ID"] == "123456789"
