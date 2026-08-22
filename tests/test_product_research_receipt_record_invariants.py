import pytest

from product_research_receipt import _validate_authoritative_records
from providers.base import EvidenceRecord


def _record(**overrides):
    values = {
        "provider": "ebay_product_research",
        "record_type": "sold",
        "source_item_id": "123456789012",
        "title": "2018 Topps Chrome Update Shohei Ohtani HMT1 PSA 10",
        "price": 105.0,
        "event_date": "2026-08-01",
        "currency": "USD",
        "payload": {"price_basis": "sold_price_plus_shipping"},
    }
    values.update(overrides)
    return EvidenceRecord(**values)


def test_authoritative_receipt_accepts_valid_sold_record():
    _validate_authoritative_records([_record()])


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"provider": "ebay_public"}, "non-authoritative provider"),
        ({"record_type": "active_listing"}, "non-sold evidence"),
        ({"currency": "CAD"}, "non-USD evidence"),
        ({"source_item_id": "not-an-id"}, "invalid stable item identity"),
        ({"event_date": None}, "without an event date"),
        ({"price": 0.0}, "non-positive landed price"),
        ({"payload": {"price_basis": "sold_price"}}, "inconsistent landed-price basis"),
    ],
)
def test_authoritative_receipt_rejects_invalid_record_semantics(overrides, message):
    with pytest.raises(ValueError, match=message):
        _validate_authoritative_records([_record(**overrides)])
