from evidence_store import EvidenceStore


CARD_ID="CURRY-2009-TOPPS-CHROME-101-PSA9"


def state(as_of, **overrides):
    value={
        "card_id":CARD_ID,
        "last_updated":as_of,
        "fair_value":100.0,
        "evidence_range":{"low":95.0,"high":105.0},
        "evidence_grade":"A",
        "confidence":0.80,
        "accepted_sales_30d":10,
        "accepted_sales_total":10,
        "accepted_active_count":2,
        "review_count":0,
        "excluded_count":0,
        "latest_sale_date":"2026-08-12",
        "action":None,
        "engine_classification":"EVIDENCE_READY",
        "blockers":[],
    }
    value.update(overrides)
    return value


def persist(store,current):
    run_id=store.start_market_run(current["last_updated"],"test")
    store.save_market_state(run_id,current)
    return run_id


def test_first_persisted_state_records_initial_reconstruction(tmp_path):
    store=EvidenceStore(tmp_path/"evidence.sqlite")
    current=state("2026-08-12T12:00:00Z")
    persist(store,current)

    persisted=store.market_history(CARD_ID)[0]
    assert persisted["reconstruction"]["has_previous"] is False
    assert persisted["reconstruction"]["change_reasons"]==["initial_observation"]


def test_large_unexplained_repricing_persists_and_fails_closed(tmp_path):
    store=EvidenceStore(tmp_path/"evidence.sqlite")
    persist(store,state("2026-08-12T12:00:00Z"))

    current=state(
        "2026-08-13T12:00:00Z",
        fair_value=120.0,
        evidence_range={"low":114.0,"high":126.0},
        action="BUY",
    )
    persist(store,current)

    persisted=store.market_history(CARD_ID)[-1]
    reconstruction=persisted["reconstruction"]
    assert reconstruction["unexplained_repricing"] is True
    assert reconstruction["reconstruction_health_failure"] is True
    assert persisted["action"] is None
    assert persisted["engine_classification"]=="RECONSTRUCTION_HEALTH_FAILURE"
    assert any("Reconstruction health failed" in blocker for blocker in persisted["blockers"])


def test_unlineaged_sold_change_cannot_explain_large_repricing(tmp_path):
    store=EvidenceStore(tmp_path/"evidence.sqlite")
    persist(store,state("2026-08-12T12:00:00Z"))

    current=state(
        "2026-08-13T12:00:00Z",
        fair_value=120.0,
        evidence_range={"low":114.0,"high":126.0},
        accepted_sales_30d=11,
        accepted_sales_total=11,
        latest_sale_date="2026-08-13",
    )
    persist(store,current)

    persisted=store.market_history(CARD_ID)[-1]
    reconstruction=persisted["reconstruction"]
    assert reconstruction["material_input_change"] is True
    assert "accepted_sales_changed_without_trusted_lineage" in reconstruction["change_reasons"]
    assert "latest_sale_changed_without_trusted_lineage" in reconstruction["change_reasons"]
    assert reconstruction["valuation_input_change"] is False
    assert reconstruction["unexplained_repricing"] is True
    assert reconstruction["reconstruction_health_failure"] is True
    assert persisted["engine_classification"]=="RECONSTRUCTION_HEALTH_FAILURE"
