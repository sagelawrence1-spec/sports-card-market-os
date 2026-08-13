from datetime import date, timedelta

from entity_matcher import SportsCardEntityMatcher
from evidence_store import EvidenceStore
from market_pipeline import ScheduledMarketPipeline
from providers.base import EvidenceRecord, ProviderResult
from providers.ebay_marketplace_insights import EbayMarketplaceInsightsProvider, INSIGHTS_SCOPE


ASSET={
    "card_id":"CURRY-2009-TOPPS-CHROME-101-PSA9",
    "observation_id":"REGISTRY-0001",
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
TITLE="2009 Topps Chrome Stephen Curry #101 Rookie PSA 9"


class SoldFixture:
    provider_name="approved_sold_fixture"

    def search_sold(self,query,**kwargs):
        today=date(2026,8,12)
        records=[EvidenceRecord(
            provider=self.provider_name,
            record_type="sold",
            source_item_id=f"sold-{index}",
            title=TITLE,
            price=4800+index*4,
            event_date=(today-timedelta(days=index)).isoformat(),
            currency="USD",
        ) for index in range(12)]
        return ProviderResult(records,query,self.provider_name)


class ActiveFixture:
    provider_name="ebay_browse_fixture"

    def search_active(self,query,**kwargs):
        records=[
            EvidenceRecord(self.provider_name,"active_listing","active-1",TITLE,4650,currency="USD"),
            EvidenceRecord(self.provider_name,"active_listing","active-2",TITLE,4995,currency="USD"),
            EvidenceRecord(self.provider_name,"active_listing","wrong-grade",TITLE.replace("PSA 9","PSA 10"),4400,currency="USD"),
        ]
        return ProviderResult(records,query,self.provider_name)


class PolicyFilteredSoldFixture:
    provider_name="licensed_sold_fixture"

    def search_sold(self,query,**kwargs):
        record=EvidenceRecord(
            provider=self.provider_name,
            record_type="sold",
            source_item_id="unconfirmed-1",
            title=TITLE,
            price=5000,
            event_date="2026-08-11",
            currency="USD",
            policy_eligible=False,
            policy_reason="price_not_confirmed",
        )
        return ProviderResult([record],query,self.provider_name)


class CappedSoldFixture(SoldFixture):
    provider_name="public_sold_fixture"
    evidence_grade_cap="B"


class OutlierSoldFixture:
    provider_name="outlier_sold_fixture"

    def search_sold(self,query,**kwargs):
        prices=[4800,4810,4820,4830,4840,4850,4860,4870,25000]
        records=[EvidenceRecord(
            provider=self.provider_name,
            record_type="sold",
            source_item_id=f"outlier-{index}",
            title=TITLE,
            price=price,
            event_date=(date(2026,8,12)-timedelta(days=index)).isoformat(),
            currency="USD",
        ) for index,price in enumerate(prices)]
        return ProviderResult(records,query,self.provider_name)


class RotatingSoldFixture(SoldFixture):
    def plan_queries(self,assets,**kwargs):
        first=dict(list(assets)[0])
        return [{"query":"first card only","assets":[first],"category_id":"261328"}]


def test_pipeline_routes_evidence_and_publishes_only_gated_value(tmp_path):
    store=EvidenceStore(tmp_path/"evidence.sqlite")
    result=ScheduledMarketPipeline(
        store,sold_provider=SoldFixture(),listing_provider=ActiveFixture()
    ).run([ASSET],as_of="2026-08-12T12:00:00Z")
    item=result.contract["items"][0]
    assert result.status=="complete"
    assert item["fair_value"] is not None
    assert item["evidence_grade"]=="A"
    assert item["accepted_sales_30d"]==12
    assert item["accepted_active_count"]==2
    assert item["excluded_count"]==1
    assert item["lowest_ask"]==4650
    assert item["action"] is None
    assert "Forward calibration" in item["blockers"][-1]
    assert len(item["evidence_ledger"]["accepted"])==12
    assert all(row["used_in_valuation"] for row in item["evidence_ledger"]["accepted"])
    assert len(store.market_history(ASSET["card_id"]))==1


def test_pipeline_fails_closed_without_authoritative_sold_source(tmp_path):
    result=ScheduledMarketPipeline(EvidenceStore(tmp_path/"evidence.sqlite")).run(
        [ASSET],as_of="2026-08-12T12:00:00Z"
    )
    item=result.contract["items"][0]
    assert result.status=="blocked_sold_source"
    assert result.contract["source"]["kind"]=="blocked_evidence"
    assert item["fair_value"] is None
    assert item["action"] is None
    assert item["engine_classification"]=="NOT_ENOUGH_EVIDENCE"


def test_pipeline_persists_but_excludes_provider_policy_failures(tmp_path):
    store=EvidenceStore(tmp_path/"evidence.sqlite")
    result=ScheduledMarketPipeline(store,sold_provider=PolicyFilteredSoldFixture()).run(
        [ASSET],as_of="2026-08-12T12:00:00Z"
    )
    item=result.contract["items"][0]
    assert result.status=="complete"
    assert item["fair_value"] is None
    assert item["excluded_count"]==1
    assert store.review_queue("rejected")[0]["match_reason"]=="provider_policy:price_not_confirmed"
    assert item["evidence_ledger"]["excluded"][0]["reason"]=="Listing did not meet the evidence rules"


def test_public_sold_result_source_cannot_claim_grade_a(tmp_path):
    result=ScheduledMarketPipeline(
        EvidenceStore(tmp_path/"evidence.sqlite"),sold_provider=CappedSoldFixture()
    ).run([ASSET],as_of="2026-08-12T12:00:00Z")
    item=result.contract["items"][0]
    assert item["fair_value"] is not None
    assert item["evidence_grade"]=="B"
    assert any("capped at evidence grade B" in blocker for blocker in item["blockers"])
    assert result.contract["source"]["provenance"]["evidence_grade_cap"]=="B"


def test_pipeline_distinguishes_accepted_sales_from_filtered_valuation_sample(tmp_path):
    result=ScheduledMarketPipeline(
        EvidenceStore(tmp_path/"evidence.sqlite"),sold_provider=OutlierSoldFixture()
    ).run([ASSET],as_of="2026-08-12T12:00:00Z")
    item=result.contract["items"][0]
    assert item["accepted_sales_total"]==9
    assert item["valuation_sample_size"]==8
    ledger=item["evidence_ledger"]["accepted"]
    assert len(ledger)==9
    assert sum(row["used_in_valuation"] for row in ledger)==8
    assert next(row for row in ledger if row["price"]==25000)["reason"].endswith("price outlier")
    assert "9 accepted USD sales; 8 used after robust outlier filtering" in item["evidence_explanation"]


def test_pipeline_marks_cards_deferred_by_free_plan_rotation(tmp_path):
    second={**ASSET,"card_id":"SECOND-CARD","observation_id":"REGISTRY-0002","player":"Second Player"}
    result=ScheduledMarketPipeline(
        EvidenceStore(tmp_path/"evidence.sqlite"),sold_provider=RotatingSoldFixture()
    ).run([ASSET,second],as_of="2026-08-12T12:00:00Z")
    items={item["card_id"]:item for item in result.contract["items"]}
    assert items[ASSET["card_id"]]["scanned_this_run"] is True
    assert items[ASSET["card_id"]]["scan_state"]=="complete"
    assert items["SECOND-CARD"]["scanned_this_run"] is False
    assert items["SECOND-CARD"]["scan_state"]=="deferred_rotation"
    assert any("later free-plan rotation" in blocker for blocker in items["SECOND-CARD"]["blockers"])


def test_marketplace_insights_parser_preserves_sold_provenance():
    provider=object.__new__(EbayMarketplaceInsightsProvider)
    provider.provider_name="ebay_marketplace_insights"
    result=provider._parse_response({"itemSales":[{
        "legacyItemId":"123",
        "title":TITLE,
        "lastSoldPrice":{"value":"4825.00","currency":"USD"},
        "lastSoldDate":"2026-08-10T00:00:00.000Z",
        "itemWebUrl":"https://www.ebay.com/itm/123",
    }]},"curry")
    assert len(result.records)==1
    assert result.records[0].record_type=="sold"
    assert result.records[0].price==4825
    assert result.records[0].event_date.startswith("2026-08-10")


def test_marketplace_insights_requests_approved_scope(monkeypatch):
    calls={}

    class OAuth:
        def get_application_token(self,scope):
            calls["scope"]=scope
            return "token"

    class Response:
        status_code=200
        def raise_for_status(self): pass
        def json(self): return {"itemSales":[]}

    monkeypatch.setattr("providers.ebay_marketplace_insights.requests.get",lambda *args,**kwargs:Response())
    EbayMarketplaceInsightsProvider(OAuth()).search_sold("curry")
    assert calls["scope"]==INSIGHTS_SCOPE


def test_same_ebay_sale_deduplicates_across_provider_surfaces(tmp_path):
    store=EvidenceStore(tmp_path/"evidence.sqlite")
    decision=SportsCardEntityMatcher().match(ASSET,TITLE)
    first=EvidenceRecord("ebay_product_research","sold","123",TITLE,4800,"2026-08-10",currency="USD")
    second=EvidenceRecord("ebay_marketplace_insights","sold","123",TITLE,4800,"2026-08-10",currency="USD")
    assert store.save(first,ASSET["card_id"],"curry",decision)==store.save(second,ASSET["card_id"],"curry",decision)
    assert len(store.accepted_sales(ASSET["card_id"]))==1
