from market_history import append_history, build_daily_brief, compact_snapshot


def contract(generated_at, **overrides):
    item={
        "card_id":"CARD-1",
        "player":"Test Player",
        "card":"2024 Test Test Player #1 · PSA 10",
        "sport":"NBA",
        "fair_value":None,
        "evidence_grade":"D",
        "confidence":30,
        "accepted_sales_total":4,
        "valuation_sample_size":4,
        "review_count":2,
        "excluded_count":6,
        "latest_sale_date":"2026-08-11",
        "scanned_this_run":True,
        "scan_state":"complete",
        "action":None,
        "evidence_ledger":{"accepted":[{"evidence_id":"raw-row"}]},
    }
    item.update(overrides)
    return {
        "generated_at":generated_at,
        "source":{"kind":"scheduled_evidence"},
        "items":[item],
    }


def test_first_snapshot_collects_a_baseline_without_inventing_changes():
    current=contract("2026-08-12T12:00:00Z")
    brief=build_daily_brief(current,None)
    assert brief["status"]=="collecting"
    assert brief["changes"]==[]
    assert brief["summary"]["review_queue"]==2


def test_daily_brief_detects_a_newly_publishable_valuation():
    previous=contract("2026-08-11T12:00:00Z")
    current=contract(
        "2026-08-12T12:00:00Z",
        fair_value=500,
        evidence_grade="B",
        accepted_sales_total=9,
        valuation_sample_size=8,
        review_count=3,
    )
    brief=build_daily_brief(current,previous)
    assert brief["status"]=="ready"
    assert brief["summary"]["new_reliable_valuations"]==1
    assert brief["changes"][0]["kind"]=="reliable"
    assert brief["changes"][0]["accepted_sales_delta"]==5


def test_daily_brief_prioritizes_withdrawn_valuation_as_weakened():
    previous=contract("2026-08-11T12:00:00Z",fair_value=500,evidence_grade="B")
    current=contract("2026-08-12T12:00:00Z",fair_value=None,evidence_grade="D")
    brief=build_daily_brief(current,previous)
    assert brief["summary"]["weakened_markets"]==1
    assert brief["changes"][0]["headline"]=="Valuation was withdrawn"


def test_history_is_compact_idempotent_and_bounded():
    previous=contract("2026-08-11T12:00:00Z")
    current=contract("2026-08-12T12:00:00Z")
    history=append_history({},current,previous=previous,limit=2)
    history=append_history(history,current,previous=previous,limit=2)
    assert [row["generated_at"] for row in history["snapshots"]]==[
        "2026-08-11T12:00:00Z",
        "2026-08-12T12:00:00Z",
    ]
    assert "evidence_ledger" not in compact_snapshot(current)["items"][0]
