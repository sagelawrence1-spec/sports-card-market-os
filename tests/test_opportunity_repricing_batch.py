from __future__ import annotations

from opportunity_repricing_batch import collect_manifest_batch
from opportunity_repricing_manifest import build_collection_manifest


def _request() -> dict:
    return {
        "candidate_rank": 1,
        "collection_priority": "P0",
        "collection_priority_reason": "fresh early-stage opportunity waiting on authoritative comps",
        "player_id": "player-one",
        "player": "Player One",
        "card_id": "card-one",
        "card_label": "Bowman Chrome Auto CPA-PO",
        "card_priority": 1,
        "stage": "ENTRY",
        "decision": "WATCH_FOR_COMPS",
        "source_type": "EBAY_PRODUCT_RESEARCH",
        "catalyst_at": "2026-08-18T10:00:00+00:00",
        "as_of": "2026-08-18T15:00:00+00:00",
        "pre_start": "2026-07-19T10:00:00+00:00",
        "post_window_end": "2026-08-25T10:00:00+00:00",
        "queryable_post_end": "2026-08-18T15:00:00+00:00",
        "status": "COLLECTION_OPEN",
        "min_pre_comps": 3,
        "min_post_comps": 3,
    }


def _manifest() -> dict:
    return build_collection_manifest(
        {
            "schema": "opportunity-repricing-plan.v1",
            "source_scan_generated_at": "2026-08-18T15:00:00+00:00",
            "as_of": "2026-08-18T15:00:00+00:00",
            "requests": [_request()],
        }
    )


def test_manifest_preserves_exact_repricing_request_for_round_trip() -> None:
    manifest = _manifest()
    item = manifest["items"][0]
    assert item["repricing_request"] == _request()
    assert item["repricing_request"]["post_window_end"] == "2026-08-25T10:00:00+00:00"
    assert item["repricing_request"]["min_pre_comps"] == 3


def test_batch_reports_missing_export_without_guessing(tmp_path) -> None:
    artifact = collect_manifest_batch(
        _manifest(),
        assets={"card-one": {"card_id": "card-one"}},
        export_dir=tmp_path,
    )
    assert artifact["ready"] is False
    assert artifact["collected_count"] == 0
    assert artifact["missing_export_count"] == 1
    assert artifact["results"][0]["status"] == "MISSING_EXPORT"


def test_batch_collects_each_manifest_item_with_exact_request(tmp_path, monkeypatch) -> None:
    manifest = _manifest()
    item = manifest["items"][0]
    (tmp_path / item["expected_export_filename"]).write_text("dummy", encoding="utf-8")
    seen: dict = {}

    def fake_collect(request, *, asset, csv_path):
        seen["request"] = dict(request)
        seen["asset"] = dict(asset)
        seen["csv_path"] = str(csv_path)
        return {"schema": "opportunity-repricing-collection.v1", "verification": {"verified": True}}

    monkeypatch.setattr("opportunity_repricing_batch.collect_repricing_verification", fake_collect)
    artifact = collect_manifest_batch(
        manifest,
        assets={"card-one": {"card_id": "card-one", "player": "Player One"}},
        export_dir=tmp_path,
    )

    assert artifact["ready"] is True
    assert artifact["collected_count"] == 1
    assert artifact["results"][0]["status"] == "COLLECTED"
    assert seen["request"] == item["repricing_request"]
    assert seen["asset"]["card_id"] == "card-one"
    assert seen["csv_path"].endswith(item["expected_export_filename"])


def test_batch_rejects_manifest_request_identity_drift(tmp_path) -> None:
    manifest = _manifest()
    manifest["items"][0]["repricing_request"] = dict(manifest["items"][0]["repricing_request"])
    manifest["items"][0]["repricing_request"]["card_id"] = "other-card"

    try:
        collect_manifest_batch(manifest, assets={}, export_dir=tmp_path)
    except ValueError as exc:
        assert "card_id must match" in str(exc)
    else:
        raise AssertionError("expected identity drift to fail closed")
