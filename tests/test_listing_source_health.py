from datetime import date, timedelta

from evidence_store import EvidenceStore
from market_pipeline import ScheduledMarketPipeline
from providers.base import EvidenceRecord, ProviderResult


BASE_ASSET={
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


class PerCardSoldFixture:
    provider_name="approved_sold_fixture"

    def search_sold(self,query,**kwargs):
        asset=kwargs["asset"]
        title=(
            f"{asset['year']} {asset['manufacturer']} {asset['set']} "
            f"{asset['player']} #{asset['card_number']} PSA {asset['grade']}"
        )
        today=date(2026,8,12)
        records=[EvidenceRecord(
            provider=self.provider_name,
            record_type="sold",
            source_item_id=f"{asset['card_id']}-sold-{index}",
            title=title,
            price=1000+index,
            event_date=(today-timedelta(days=index)).isoformat(),
            currency="USD",
        ) for index in range(12)]
        return ProviderResult(records,query,self.provider_name)


class PartialActiveFixture:
    provider_name="ebay_browse_fixture"

    def search_active(self,query,**kwargs):
        if "Second Player" in query:
            raise RuntimeError("simulated listing outage")
        return ProviderResult([
            EvidenceRecord(
                self.provider_name,
                "active_listing",
                "active-curry",
                "2009 Topps Chrome Stephen Curry #101 PSA 9",
                1250,
                currency="USD",
            )
        ],query,self.provider_name)


def test_active_listing_failure_is_isolated_to_affected_card(tmp_path):
    second={
        **BASE_ASSET,
        "card_id":"SECOND-2010-TOPPS-CHROME-55-PSA9",
        "observation_id":"REGISTRY-0002",
        "player":"Second Player",
        "year":2010,
        "card_number":"55",
    }
    result=ScheduledMarketPipeline(
        EvidenceStore(tmp_path/"evidence.sqlite"),
        sold_provider=PerCardSoldFixture(),
        listing_provider=PartialActiveFixture(),
    ).run([BASE_ASSET,second],as_of="2026-08-12T12:00:00Z")

    items={item["card_id"]:item for item in result.contract["items"]}
    curry=items[BASE_ASSET["card_id"]]
    failed=items[second["card_id"]]

    assert result.status=="complete"
    assert curry["listing_source_available"] is True
    assert curry["accepted_active_count"]==1
    assert not any("Active-listing query failed" in blocker for blocker in curry["blockers"])

    assert failed["listing_source_available"] is False
    assert failed["accepted_active_count"]==0
    assert any("Active-listing query failed" in blocker for blocker in failed["blockers"])

    provenance=result.contract["source"]["provenance"]
    assert provenance["listing_source_available"] is True
    assert provenance["listing_source_partial"] is True
    assert provenance["listing_queries_completed"]==[BASE_ASSET["card_id"]]
    assert provenance["listing_queries_failed"]==[second["card_id"]]
