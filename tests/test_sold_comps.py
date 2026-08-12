import pytest

from market_runner import configured_sold_provider
from providers.sold_comps import SALES_URL, SoldCompsProvider


TITLE="2009 Topps Chrome Stephen Curry #101 Rookie PSA 9"


def sold_item(**updates):
    item={
        "itemId":"123",
        "title":TITLE,
        "listingType":"sold",
        "endedAt":"2026-08-10",
        "soldPrice":"4825.00",
        "soldCurrency":"USD",
        "shippingPrice":"12.50",
        "shippingCurrency":"USD",
        "totalPrice":"4837.50",
        "bestOfferAccepted":False,
        "url":"https://www.ebay.com/itm/123?nordt=true",
    }
    item.update(updates)
    return item


def test_parser_accepts_buyer_cost_with_shipping():
    result=SoldCompsProvider("key")._parse_response({"items":[sold_item()]},"curry")
    record=result.records[0]
    assert record.policy_eligible
    assert record.source_item_id=="ebay:123"
    assert record.price==4837.50
    assert record.payload["price_basis"]=="sold_price_plus_shipping"


@pytest.mark.parametrize(("updates","reason"),[
    ({"bestOfferAccepted":True},"best_offer_price_is_upper_bound"),
    ({"shippingPrice":None},"shipping_price_unknown"),
    ({"soldCurrency":"CAD"},"non_usd_currency"),
    ({"totalPrice":"4900.00"},"inconsistent_total_price"),
    ({"listingType":"active"},"not_a_sold_listing"),
])
def test_parser_keeps_unusable_rows_for_audit(updates,reason):
    record=SoldCompsProvider("key")._parse_response({"items":[sold_item(**updates)]},"curry").records[0]
    assert not record.policy_eligible
    assert record.policy_reason==reason


def test_missing_ids_receive_distinct_stable_audit_ids():
    items=[
        sold_item(itemId=None,title="First malformed row"),
        sold_item(itemId=None,title="Second malformed row"),
    ]
    first=SoldCompsProvider("key")._parse_response({"items":items},"curry").records
    second=SoldCompsProvider("key")._parse_response({"items":items},"curry").records
    assert first[0].policy_reason=="missing_source_id"
    assert first[0].source_item_id!=first[1].source_item_id
    assert [record.source_item_id for record in first]==[record.source_item_id for record in second]


def test_search_uses_sold_complete_listing_filters_and_secret_header():
    calls={}

    class Response:
        status_code=200
        headers={"X-RateLimit-Remaining":"99"}
        def raise_for_status(self): pass
        def json(self): return {"items":[sold_item()]}

    class Session:
        def get(self,url,**kwargs):
            calls.update({"url":url,**kwargs})
            return Response()

    result=SoldCompsProvider("secret",session=Session()).search_sold(
        "curry psa 9",category_id="261328",date_from="2026-08-01"
    )
    assert calls["url"]==SALES_URL
    assert calls["headers"]=={"Authorization":"Bearer secret"}
    assert calls["params"]["sold"]=="true"
    assert calls["params"]["includeCompleteListing"]=="true"
    assert calls["params"]["categoryId"]=="261328"
    assert calls["params"]["soldAfter"]=="2026-08-01"
    assert result.metadata["rate_limit"]["remaining"]=="99"


def test_query_planner_groups_cards_and_rotates_within_allowance():
    assets=[
        {"card_id":"curry-1","player":"Stephen Curry","year":2009,"grade_company":"PSA","grade":9},
        {"card_id":"curry-2","player":"Stephen Curry","year":2009,"grade_company":"PSA","grade":9},
        {"card_id":"ohtani-1","player":"Shohei Ohtani","year":2018,"grade_company":"PSA","grade":10},
    ]
    plans=SoldCompsProvider("key",max_queries_per_run=1).plan_queries(
        assets,as_of="2026-08-12T12:00:00Z"
    )
    assert len(plans)==1
    assert len(plans[0]["assets"]) in {1,2}
    assert "-reprint -lot -break" in plans[0]["query"]


def test_runner_accepts_free_sold_comps_key(monkeypatch):
    class OAuth:
        def configured(self): return False

    monkeypatch.setenv("MARKET_SOLD_PROVIDER","sold_comps")
    monkeypatch.setenv("SOLD_COMPS_API_KEY","secret")
    monkeypatch.setenv("SOLD_COMPS_MAX_QUERIES_PER_RUN","2")
    provider=configured_sold_provider(OAuth(),"EBAY_US")
    assert isinstance(provider,SoldCompsProvider)
    assert provider.max_queries_per_run==2


def test_runner_uses_safe_defaults_for_empty_optional_variables(monkeypatch):
    class OAuth:
        def configured(self): return False

    monkeypatch.setenv("MARKET_SOLD_PROVIDER","sold_comps")
    monkeypatch.setenv("SOLD_COMPS_API_KEY","secret")
    monkeypatch.setenv("SOLD_COMPS_EBAY_SITE","")
    monkeypatch.setenv("SOLD_COMPS_MAX_QUERIES_PER_RUN","")
    provider=configured_sold_provider(OAuth(),"EBAY_US")
    assert provider.ebay_site=="ebay.com"
    assert provider.max_queries_per_run==3
