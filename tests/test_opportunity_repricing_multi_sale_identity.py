import csv

from opportunity_repricing_collection import collect_repricing_verification


def _asset():
    return {"card_id":"c1","player":"Player One","year":2026,"manufacturer":"Topps","set_name":"Topps Chrome","card_number":"10","parallel":"base","autograph":0}


def _request():
    return {"source_type":"EBAY_PRODUCT_RESEARCH","player_id":"p1","card_id":"c1","catalyst_at":"2026-08-10T12:00:00+00:00","pre_start":"2026-07-11T12:00:00+00:00","post_window_end":"2026-08-17T12:00:00+00:00","queryable_post_end":"2026-08-17T12:00:00+00:00","as_of":"2026-08-18T12:00:00+00:00","min_pre_comps":3,"min_post_comps":3}


def test_repricing_keeps_distinct_sale_days_from_same_multi_quantity_listing(tmp_path):
    path=tmp_path/"sold.csv"
    fields=["Item Title","Sold Price","Shipping","Sold Date","Item ID","Currency"]
    rows=[("2026-08-01","100","111"),("2026-08-03","105","111"),("2026-08-05","110","111"),("2026-08-11","115","222"),("2026-08-12","120","222"),("2026-08-13","125","222")]
    with path.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields); writer.writeheader()
        for sold_date,price,item_id in rows:
            writer.writerow({"Item Title":"2026 Topps Chrome Player One #10","Sold Price":f"${price}","Shipping":"$0.00","Sold Date":sold_date,"Item ID":item_id,"Currency":"USD"})
    result=collect_repricing_verification(_request(),asset=_asset(),csv_path=path)
    assert result["verification"]["verified"] is True
    assert result["verification"]["pre_count"]==3 and result["verification"]["post_count"]==3
    ids=result["verification"]["evidence_ids"]
    assert len(ids)==6
    assert "ebay_product_research:111:2026-08-01" in ids
    assert "ebay_product_research:111:2026-08-03" in ids
    assert "ebay_product_research:222:2026-08-13" in ids
