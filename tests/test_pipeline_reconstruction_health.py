from evidence_store import EvidenceStore
from market_pipeline import ScheduledMarketPipeline


ASSET={
    "card_id":"TEST-2024-TOPPS-1-RAW",
    "year":"2024",
    "manufacturer":"Topps",
    "set":"Topps",
    "player":"Test Player",
    "card_number":"1",
    "parallel":"Base",
}


def test_pipeline_exposes_initial_universe_reconstruction_health(tmp_path):
    store=EvidenceStore(tmp_path/"evidence.sqlite")
    pipeline=ScheduledMarketPipeline(store)

    result=pipeline.run([ASSET],as_of="2026-08-13T12:00:00+00:00")

    health=result.contract["reconstruction_health"]
    assert health["status"]=="healthy"
    assert health["total_cards"]==1
    assert health["cards_with_previous"]==0
    assert health["initial_observations"]==1
    assert health["cards_requiring_review"]==[]
    assert result.contract["source"]["provenance"]["reconstruction_health"]==health


def test_pipeline_health_tracks_cards_with_previous_without_false_drift(tmp_path):
    store=EvidenceStore(tmp_path/"evidence.sqlite")
    pipeline=ScheduledMarketPipeline(store)

    pipeline.run([ASSET],as_of="2026-08-13T12:00:00+00:00")
    result=pipeline.run([ASSET],as_of="2026-08-14T12:00:00+00:00")

    health=result.contract["reconstruction_health"]
    assert health["status"]=="healthy"
    assert health["cards_with_previous"]==1
    assert health["initial_observations"]==0
    assert health["unexplained_repricing_count"]==0
    assert health["hard_failure_count"]==0
