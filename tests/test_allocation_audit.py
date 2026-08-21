import pytest

from allocation_audit import AllocationAuditStore, persist_allocation_run


def test_persists_approved_and_blocked_decisions(tmp_path):
    store = AllocationAuditStore(tmp_path / "market.sqlite")
    rows = [
        {
            "card_id": "a",
            "action": "BUY",
            "allocation": 1000,
            "exposure_adjusted_allocation": 700,
            "ready": True,
            "blockers": [],
            "exposure_blockers": [],
            "evidence_grade": "A",
            "confidence": 0.91,
            "upside": 0.25,
        },
        {
            "card_id": "b",
            "action": "BUY",
            "allocation": 0,
            "ready": False,
            "blockers": ["segment_sample_too_small"],
            "exposure_blockers": [],
            "evidence_grade": "B",
            "confidence": 0.72,
        },
    ]
    assert persist_allocation_run(
        store,
        run_id="run-1",
        allocations=rows,
        decided_at="2026-08-14T12:00:00Z",
    ) == 2
    loaded = store.load_run("run-1")
    assert loaded[0].approved_allocation == 700
    assert loaded[1].blockers == ("segment_sample_too_small",)


def test_audit_never_increases_allocation(tmp_path):
    store = AllocationAuditStore(tmp_path / "market.sqlite")
    with pytest.raises(ValueError):
        persist_allocation_run(
            store,
            run_id="run-1",
            allocations=[{
                "card_id": "a",
                "allocation": 500,
                "exposure_adjusted_allocation": 600,
                "ready": True,
            }],
        )


def test_identical_retry_is_idempotent_and_preserves_original_timestamp(tmp_path):
    store = AllocationAuditStore(tmp_path / "market.sqlite")
    row = {
        "card_id": "a",
        "allocation": 500,
        "exposure_adjusted_allocation": 400,
        "ready": True,
        "exposure_blockers": [],
    }
    persist_allocation_run(
        store,
        run_id="run-1",
        allocations=[row],
        decided_at="2026-08-14T12:00:00Z",
    )
    persist_allocation_run(
        store,
        run_id="run-1",
        allocations=[row],
        decided_at="2026-08-15T12:00:00Z",
    )
    loaded = store.load_run("run-1")
    assert len(loaded) == 1
    assert loaded[0].approved_allocation == 400
    assert loaded[0].decided_at == "2026-08-14T12:00:00Z"


def test_recorded_allocation_cannot_be_rewritten(tmp_path):
    store = AllocationAuditStore(tmp_path / "market.sqlite")
    persist_allocation_run(
        store,
        run_id="run-1",
        allocations=[{
            "card_id": "a",
            "allocation": 500,
            "exposure_adjusted_allocation": 400,
            "ready": True,
        }],
        decided_at="2026-08-14T12:00:00Z",
    )

    with pytest.raises(ValueError, match="immutable"):
        persist_allocation_run(
            store,
            run_id="run-1",
            allocations=[{
                "card_id": "a",
                "allocation": 500,
                "exposure_adjusted_allocation": 300,
                "ready": True,
                "exposure_blockers": ["player_cap_reached"],
            }],
            decided_at="2026-08-15T12:00:00Z",
        )

    loaded = store.load_run("run-1")
    assert len(loaded) == 1
    assert loaded[0].approved_allocation == 400
    assert loaded[0].exposure_blockers == ()


def test_missing_card_id_is_skipped(tmp_path):
    store = AllocationAuditStore(tmp_path / "market.sqlite")
    assert persist_allocation_run(
        store,
        run_id="run-1",
        allocations=[{"allocation": 100}],
    ) == 0
    assert store.load_run("run-1") == []
