from evidence_store import EvidenceStore
from market_pipeline import ScheduledMarketPipeline
from providers.base import EvidenceRecord, ProviderResult


CURRY={
    "card_id":"CURRY-2009-TOPPS-CHROME-101-PSA9",
    "observation_id":"REGISTRY-CURRY",
    "sport":"Basketball",
    "league":"NBA",
    "player":"Stephen Curry",
    "year":2009,
    "manufacturer":"Topps",
    "set":"Chrome",
    "card_number":"101",
    "parallel":"Base",
    "autograph":0,
    "grade_company":"PSA",
    "grade":9,
    "ebay_category_id":"261328",
}
JUDGE={
    "card_id":"JUDGE-2017-TOPPS-CHROME-169-PSA9",
    "observation_id":"REGISTRY-JUDGE",
    "sport":"Baseball",
    "league":"MLB",
    "player":"Aaron Judge",
    "year":2017,
    "manufacturer":"Topps",
    "set":"Chrome",
    "card_number":"169",
    "parallel":"Base",
    "autograph":0,
    "grade_company":"PSA",
    "grade":9,
    "ebay_category_id":"261328",
}
JUDGE_TITLE="2017 Topps Chrome Aaron Judge #169 Rookie PSA 9"


class CurryScopedSoldFixture:
    provider_name="query_scope_sold_fixture"

    def plan_queries(self,assets,**kwargs):
        return [{"query":"Stephen Curry 2009 Topps Chrome 101 PSA 9","assets":[dict(assets[0])],"category_id":"261328"}]

    def search_sold(self,query,**kwargs):
        return ProviderResult([
            EvidenceRecord(
                self.provider_name,"sold","wrong-query-judge",JUDGE_TITLE,500,
                event_date="2026-08-12",currency="USD",
            )
        ],query,self.provider_name)


class CrossRouteActiveFixture:
    provider_name="query_scope_active_fixture"

    def search_active(self,query,**kwargs):
        if "Aaron Judge" in query:
            raise RuntimeError("Judge query intentionally unavailable")
        return ProviderResult([
            EvidenceRecord(
                self.provider_name,"active_listing","wrong-query-judge-active",
                JUDGE_TITLE,550,currency="USD",
            )
        ],query,self.provider_name)


def test_sold_result_cannot_attach_to_unqueried_registry_card(tmp_path):
    store=EvidenceStore(tmp_path/"evidence.sqlite")
    result=ScheduledMarketPipeline(store,sold_provider=CurryScopedSoldFixture()).run(
        [CURRY,JUDGE],as_of="2026-08-12T12:00:00Z"
    )
    items={item["card_id"]:item for item in result.contract["items"]}

    assert items[CURRY["card_id"]]["scan_state"]=="complete"
    assert items[JUDGE["card_id"]]["scan_state"]=="deferred_rotation"
    assert store.accepted_sales(JUDGE["card_id"])==[]
    assert items[JUDGE["card_id"]]["accepted_sales_total"]==0
    assert items[CURRY["card_id"]]["excluded_count"]==1


def test_active_result_cannot_attach_to_different_query_card(tmp_path):
    store=EvidenceStore(tmp_path/"evidence.sqlite")
    result=ScheduledMarketPipeline(store,listing_provider=CrossRouteActiveFixture()).run(
        [CURRY,JUDGE],as_of="2026-08-12T12:00:00Z"
    )
    items={item["card_id"]:item for item in result.contract["items"]}

    assert items[JUDGE["card_id"]]["accepted_active_count"]==0
    assert items[CURRY["card_id"]]["accepted_active_count"]==0
    assert any(error.startswith(f"active:{JUDGE['card_id']}:") for error in result.errors)
