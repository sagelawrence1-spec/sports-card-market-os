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
SECOND={
    **BASE_ASSET,
    "card_id":"JUDGE-2017-TOPPS-CHROME-169-PSA9",
    "observation_id":"REGISTRY-0002",
    "sport":"Baseball",
    "league":"MLB",
    "player":"Aaron Judge",
    "year":2017,
    "card_number":"169",
}


def _title(asset):
    return f"{asset['year']} Topps Chrome {asset['player']} #{asset['card_number']} PSA 9"


class PartialFailureSoldFixture:
    provider_name="partial_failure_fixture"

    def plan_queries(self, assets, **kwargs):
        return [
            {"query":"curry", "assets":[assets[0]], "category_id":"261328"},
            {"query":"judge", "assets":[assets[1]], "category_id":"261328"},
        ]

    def search_sold(self, query, **kwargs):
        if query == "judge":
            raise RuntimeError("upstream timeout")
        asset=kwargs["asset"]
        today=date(2026,8,12)
        records=[EvidenceRecord(
            provider=self.provider_name,
            record_type="sold",
            source_item_id=f"curry-{index}",
            title=_title(asset),
            price=4800+index*4,
            event_date=(today-timedelta(days=index)).isoformat(),
            currency="USD",
        ) for index in range(12)]
        return ProviderResult(records,query,self.provider_name)


def test_partial_sold_failure_does_not_poison_healthy_card(tmp_path):
    result=ScheduledMarketPipeline(
        EvidenceStore(tmp_path/"evidence.sqlite"),
        sold_provider=PartialFailureSoldFixture(),
    ).run([BASE_ASSET,SECOND],as_of="2026-08-12T12:00:00Z")

    items={item["card_id"]:item for item in result.contract["items"]}
    healthy=items[BASE_ASSET["card_id"]]
    failed=items[SECOND["card_id"]]

    assert result.status=="partial_sold_source"
    assert healthy["scan_state"]=="complete"
    assert healthy["fair_value"] is not None
    assert not any("sold-data source is unavailable" in blocker for blocker in healthy["blockers"])

    assert failed["scan_state"]=="failed"
    assert failed["fair_value"] is None
    assert any("query failed for this card" in blocker for blocker in failed["blockers"])


def test_partial_failure_is_explicit_in_provenance(tmp_path):
    result=ScheduledMarketPipeline(
        EvidenceStore(tmp_path/"evidence.sqlite"),
        sold_provider=PartialFailureSoldFixture(),
    ).run([BASE_ASSET,SECOND],as_of="2026-08-12T12:00:00Z")

    provenance=result.contract["source"]["provenance"]
    assert provenance["sold_source_available"] is True
    assert provenance["sold_source_partial"] is True
    assert provenance["sold_queries_failed"]==[SECOND["card_id"]]
    assert provenance["sold_queries_completed"]==[BASE_ASSET["card_id"]]
