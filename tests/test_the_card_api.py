from datetime import date

import pytest

from evidence_store import EvidenceStore
from entity_matcher import SportsCardEntityMatcher
from market_runner import configured_sold_provider
from providers.base import EvidenceRecord
from providers.the_card_api import SALES_URL, TheCardApiSoldProvider


TITLE="2009 Topps Chrome Stephen Curry #101 Rookie PSA 9"
ASSET={
    "card_id":"CURRY-2009-TOPPS-CHROME-101-PSA9",
    "player":"Stephen Curry",
    "year":2009,
    "manufacturer":"Topps",
    "set":"Chrome",
    "card_number":"101",
    "parallel":"Base",
    "autograph":0,
    "grade_company":"PSA",
    "grade":9,
}


def sale(**updates):
    item={
        "id":"ebay-123",
        "platform":"eBay",
        "listing_type":"best_offer",
        "title":TITLE,
        "sale_date":"2026-08-10",
        "sold_at":"2026-08-10T00:00:00Z",
        "price":4825,
        "currency":"USD",
        "price_confirmed":True,
        "listing_url":"https://www.ebay.com/itm/123",
    }
    item.update(updates)
    return item


def test_parser_accepts_only_confirmed_current_usd_sale():
    provider=TheCardApiSoldProvider("key")
    result=provider._parse_response({"data":[sale()]},"curry")
    record=result.records[0]
    assert record.policy_eligible
    assert record.source_item_id=="ebay:123"
    assert record.price==4825
    assert record.payload["price_basis"]=="reported_final_price"


@pytest.mark.parametrize(("updates","reason"),[
    ({"price_confirmed":False},"price_not_confirmed"),
    ({"currency":"CAD"},"non_usd_currency"),
    ({"sale_date":"2026-07-31","sold_at":"2026-07-31T00:00:00Z"},"historical_currency_provenance_untrusted"),
    ({"price":0},"invalid_price"),
])
def test_parser_keeps_ineligible_sales_for_audit(updates,reason):
    record=TheCardApiSoldProvider("key")._parse_response({"data":[sale(**updates)]},"curry").records[0]
    assert not record.policy_eligible
    assert record.policy_reason==reason


def test_goldin_hammer_requires_explicit_normalization():
    item=sale(id="goldin-456",platform="Goldin",price=1000)
    blocked=TheCardApiSoldProvider("key",platforms=("goldin",))._parse_response({"data":[item]},"curry").records[0]
    normalized=TheCardApiSoldProvider(
        "key",platforms=("goldin",),goldin_buyer_premium=.22
    )._parse_response({"data":[item]},"curry").records[0]
    assert blocked.policy_reason=="unnormalized_hammer_price"
    assert normalized.policy_eligible and normalized.price==1220
    assert normalized.payload["price_basis"]=="hammer_plus_configured_buyer_premium"


def test_search_applies_identity_filters_and_secret_header():
    calls={}

    class Response:
        status_code=200
        headers={"X-RateLimit-Remaining":"4999"}
        def raise_for_status(self): pass
        def json(self): return {"data":[sale()],"pagination":{},"meta":{}}

    class Session:
        def get(self,url,**kwargs):
            calls.update({"url":url,**kwargs})
            return Response()

    result=TheCardApiSoldProvider("secret",session=Session()).search_sold("curry chrome",asset=ASSET)
    assert calls["url"]==SALES_URL
    assert calls["headers"]=={"x-market-api-key":"secret"}
    assert calls["params"]["platform"]=="ebay"
    assert calls["params"]["category"]=="sports"
    assert calls["params"]["grader"]=="PSA"
    assert calls["params"]["grade"]=="9"
    assert result.metadata["rate_limit"]["remaining"]=="4999"


def test_auction_house_query_does_not_require_unavailable_category_backfill():
    calls=[]

    class Response:
        status_code=200
        headers={}
        def raise_for_status(self): pass
        def json(self): return {"data":[],"pagination":{},"meta":{}}

    class Session:
        def get(self,_url,**kwargs):
            calls.append(kwargs["params"])
            return Response()

    TheCardApiSoldProvider("secret",platforms=("goldin",),session=Session()).search_sold("curry chrome")
    assert "category" not in calls[0]


def test_paid_plan_is_required_before_persistent_runner_use(monkeypatch):
    class OAuth:
        def configured(self): return False

    monkeypatch.setenv("MARKET_SOLD_PROVIDER","the_card_api")
    monkeypatch.setenv("THE_CARD_API_KEY","secret")
    monkeypatch.setenv("THE_CARD_API_PLAN","free")
    with pytest.raises(RuntimeError,match="paid The Card API plan"):
        configured_sold_provider(OAuth(),"EBAY_US")

    monkeypatch.setenv("THE_CARD_API_PLAN","starter")
    provider=configured_sold_provider(OAuth(),"EBAY_US")
    assert isinstance(provider,TheCardApiSoldProvider)


def test_same_ebay_sale_deduplicates_with_official_provider(tmp_path):
    store=EvidenceStore(tmp_path/"evidence.sqlite")
    decision=SportsCardEntityMatcher().match(ASSET,TITLE)
    official=EvidenceRecord("ebay_marketplace_insights","sold","123",TITLE,4825,"2026-08-10",currency="USD")
    licensed=TheCardApiSoldProvider("key")._parse_response({"data":[sale()]},"curry").records[0]
    assert store.save(official,ASSET["card_id"],"curry",decision)==store.save(licensed,ASSET["card_id"],"curry",decision)
    assert len(store.accepted_sales(ASSET["card_id"]))==1
