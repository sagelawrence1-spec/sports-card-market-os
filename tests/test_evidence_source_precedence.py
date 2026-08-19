from entity_matcher import MatchDecision
from evidence_store import EvidenceStore
from providers.base import EvidenceRecord


def _record(provider, *, item_id="1234567890", price=100.0, source_platform="ebay", event_date="2026-08-01"):
    return EvidenceRecord(
        provider=provider,
        record_type="sold",
        source_item_id=item_id,
        title="2024 Topps Chrome Shohei Ohtani #1 PSA 10",
        price=price,
        event_date=event_date,
        currency="USD",
        payload={"source_platform": source_platform},
    )


def _accepted():
    return MatchDecision(True, 95.0, "accepted", {})


def _rejected():
    return MatchDecision(False, 0.0, "provider_policy:best_offer_price_is_upper_bound", {})


def test_weaker_provider_cannot_overwrite_authoritative_accepted_sale(tmp_path):
    store=EvidenceStore(tmp_path / "market.sqlite")
    eid=store.save(
        _record("ebay_product_research", price=100.0),
        "card-1",
        "ohtani",
        _accepted(),
    )
    same_eid=store.save(
        _record("sold_comps", price=999.0),
        "card-1",
        "ohtani",
        _rejected(),
    )

    assert same_eid == eid
    row=store.conn.execute("SELECT * FROM source_evidence WHERE evidence_id=?",(eid,)).fetchone()
    assert row["provider"] == "ebay_product_research"
    assert row["match_status"] == "accepted"
    assert row["price"] == 100.0


def test_authoritative_provider_replaces_weaker_duplicate(tmp_path):
    store=EvidenceStore(tmp_path / "market.sqlite")
    eid=store.save(
        _record("sold_comps", price=999.0),
        "card-1",
        "ohtani",
        _rejected(),
    )
    same_eid=store.save(
        _record("ebay_product_research", price=100.0),
        "card-1",
        "ohtani",
        _accepted(),
    )

    assert same_eid == eid
    row=store.conn.execute("SELECT * FROM source_evidence WHERE evidence_id=?",(eid,)).fetchone()
    assert row["provider"] == "ebay_product_research"
    assert row["match_status"] == "accepted"
    assert row["price"] == 100.0


def test_same_provider_can_correct_its_own_prior_decision(tmp_path):
    store=EvidenceStore(tmp_path / "market.sqlite")
    eid=store.save(
        _record("ebay_product_research", price=100.0),
        "card-1",
        "ohtani",
        _accepted(),
    )
    store.save(
        _record("ebay_product_research", price=100.0),
        "card-1",
        "ohtani",
        _rejected(),
    )

    row=store.conn.execute("SELECT * FROM source_evidence WHERE evidence_id=?",(eid,)).fetchone()
    assert row["provider"] == "ebay_product_research"
    assert row["match_status"] == "rejected"


def test_normalized_ebay_item_id_is_stored_consistently(tmp_path):
    store=EvidenceStore(tmp_path / "market.sqlite")
    eid=store.save(
        _record("sold_comps", item_id="ebay:1234567890"),
        "card-1",
        "ohtani",
        _accepted(),
    )

    row=store.conn.execute("SELECT source_item_id FROM source_evidence WHERE evidence_id=?",(eid,)).fetchone()
    assert row["source_item_id"] == "1234567890"


def test_multi_quantity_listing_sales_on_distinct_days_persist_as_distinct_evidence(tmp_path):
    store=EvidenceStore(tmp_path / "market.sqlite")
    first=store.save(
        _record("ebay_product_research", item_id="1234567890", price=100.0, event_date="2026-08-01"),
        "card-1",
        "ohtani",
        _accepted(),
    )
    second=store.save(
        _record("ebay_product_research", item_id="1234567890", price=115.0, event_date="2026-08-03"),
        "card-1",
        "ohtani",
        _accepted(),
    )

    assert first != second
    rows=store.accepted_sales("card-1")
    assert len(rows) == 2
    assert {row["event_date"] for row in rows} == {"2026-08-01", "2026-08-03"}
    assert {row["price"] for row in rows} == {100.0, 115.0}


def test_same_listing_same_sold_day_retains_provider_precedence_identity(tmp_path):
    store=EvidenceStore(tmp_path / "market.sqlite")
    weak=store.save(
        _record("sold_comps", item_id="1234567890", price=999.0, event_date="2026-08-01"),
        "card-1",
        "ohtani",
        _rejected(),
    )
    strong=store.save(
        _record("ebay_product_research", item_id="1234567890", price=100.0, event_date="2026-08-01"),
        "card-1",
        "ohtani",
        _accepted(),
    )

    assert strong == weak
    row=store.conn.execute("SELECT * FROM source_evidence WHERE evidence_id=?",(strong,)).fetchone()
    assert row["provider"] == "ebay_product_research"
    assert row["price"] == 100.0
