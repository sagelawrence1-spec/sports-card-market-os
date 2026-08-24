from datetime import date

from recommendation_journal import (
    RecommendationJournal,
    capture_recommendations,
    grade_outcomes,
    outcome_summary,
    settle_outcomes,
)


def _contract(as_of, *, action="BUY", sales=None, fair_value=120):
    sales=sales or []
    return {
        "generated_at":f"{as_of}T12:00:00",
        "items":[{
            "observation_id":"obs-1",
            "card_id":"card-1",
            "action":action,
            "fair_value":fair_value,
            "confidence":0.8,
            "evidence_grade":"A",
            "thesis":"mispriced relative to evidence",
            "last_updated":f"{as_of}T12:00:00",
            "evidence_ledger":{"accepted":[
                {"price":p,"currency":c,"event_date":d,"used_in_valuation":used}
                for p,d,c,used in sales
            ]},
        }],
    }


def test_capture_is_point_in_time_and_uses_latest_observable_sale(tmp_path):
    journal=RecommendationJournal(tmp_path/"market.sqlite")
    contract=_contract("2026-01-10",sales=[
        (100,"2026-01-01","USD",True),
        (110,"2026-01-08","USD",True),
        (999,"2026-01-11","USD",True),
    ])
    assert capture_recommendations(journal,contract)==1
    row=journal.load()[0]
    assert row.entry_price==110
    assert row.fair_value==120


def test_non_action_and_future_only_evidence_do_not_create_calls(tmp_path):
    journal=RecommendationJournal(tmp_path/"market.sqlite")
    assert capture_recommendations(journal,_contract("2026-01-10",action=None,sales=[(100,"2026-01-01","USD",True)]))==0
    assert capture_recommendations(journal,_contract("2026-01-10",sales=[(999,"2026-01-11","USD",True)]))==0
    assert journal.load()==[]


def test_outcome_settlement_requires_full_horizon_and_bounds_future_sales(tmp_path):
    journal=RecommendationJournal(tmp_path/"market.sqlite")
    capture_recommendations(journal,_contract("2026-01-01",sales=[(100,"2025-12-31","USD",True)]),horizon_days=30)
    assert settle_outcomes(journal,_contract("2026-01-20",sales=[(150,"2026-01-20","USD",True)]))==0
    mature=_contract("2026-02-01",sales=[
        (130,"2026-01-31","USD",True),
        (140,"2026-02-01","USD",True),
        (999,"2026-02-02","USD",True),
    ])
    assert settle_outcomes(journal,mature)==1
    row=journal.load()[0]
    assert row.realized_price==130
    assert row.realized_at==date(2026,1,31)


def test_summary_scores_sell_direction_correctly(tmp_path):
    journal=RecommendationJournal(tmp_path/"market.sqlite")
    capture_recommendations(
        journal,
        _contract("2026-01-01",action="SELL",fair_value=80,sales=[(100,"2025-12-31","USD",True)]),
        horizon_days=30,
    )
    settle_outcomes(journal,_contract("2026-02-01",action="SELL",fair_value=80,sales=[(80,"2026-01-31","USD",True)]))
    summary=outcome_summary(journal)
    assert summary["settled"]==1
    assert summary["hit_rate"]==1.0
    assert summary["median_return"]==0.2
    assert summary["thesis_correctness"]==1.0


def test_grade_outcomes_reports_realized_return_and_thesis_correctness(tmp_path):
    journal=RecommendationJournal(tmp_path/"market.sqlite")
    capture_recommendations(
        journal,
        _contract("2026-01-01",fair_value=125,sales=[(100,"2025-12-31","USD",True)]),
        horizon_days=30,
    )
    settle_outcomes(journal,_contract("2026-02-01",fair_value=125,sales=[(110,"2026-01-31","USD",True)]))

    grades=grade_outcomes(journal)
    assert grades==[{
        "observation_id":"obs-1",
        "card_id":"card-1",
        "as_of_date":"2026-01-01",
        "horizon_days":30,
        "realized_at":"2026-01-31",
        "entry_price":100.0,
        "fair_value":125.0,
        "realized_price":110.0,
        "realized_return":0.1,
        "signed_return":0.1,
        "thesis_correct":True,
    }]


def test_thesis_grade_uses_published_fair_value_not_hindsight_text(tmp_path):
    journal=RecommendationJournal(tmp_path/"market.sqlite")
    capture_recommendations(
        journal,
        _contract("2026-01-01",fair_value=125,sales=[(100,"2025-12-31","USD",True)]),
        horizon_days=30,
    )
    settle_outcomes(journal,_contract("2026-02-01",fair_value=1,sales=[(90,"2026-01-31","USD",True)]))

    grades=grade_outcomes(journal)
    assert grades[0]["fair_value"]==125.0
    assert grades[0]["realized_return"]==-0.1
    assert grades[0]["thesis_correct"] is False
    assert outcome_summary(journal)["thesis_correctness"]==0.0


def test_unsettled_calls_do_not_receive_outcome_grades(tmp_path):
    journal=RecommendationJournal(tmp_path/"market.sqlite")
    capture_recommendations(
        journal,
        _contract("2026-01-01",sales=[(100,"2025-12-31","USD",True)]),
        horizon_days=30,
    )
    assert grade_outcomes(journal)==[]
    assert outcome_summary(journal)=={
        "settled":0,
        "hit_rate":None,
        "median_return":None,
        "thesis_correctness":None,
    }
