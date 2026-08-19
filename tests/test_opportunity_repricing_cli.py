import csv
import io
import json
from contextlib import redirect_stderr

from opportunity_repricing_cli import main


def _request():
    return {
        "player_id": "player-1",
        "card_id": "card-10",
        "source_type": "EBAY_PRODUCT_RESEARCH",
        "catalyst_at": "2026-08-10T12:00:00+00:00",
        "as_of": "2026-08-18T10:00:00+00:00",
        "pre_start": "2026-07-11T12:00:00+00:00",
        "post_window_end": "2026-08-17T12:00:00+00:00",
        "min_pre_comps": 3,
        "min_post_comps": 3,
    }


def _asset():
    return {"card_id":"card-10","player":"Player One","year":2026,"manufacturer":"Topps","set_name":"Topps Chrome","card_number":"10","parallel":"base","autograph":0}


def _write_csv(path):
    rows=[(1,"2026-08-01",100),(2,"2026-08-02",110),(3,"2026-08-03",120),(4,"2026-08-11",130),(5,"2026-08-12",140),(6,"2026-08-13",150)]
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=["Title","Sold Price","Shipping","Sold Date","Item ID","Currency"]); writer.writeheader()
        for item_id,sold_date,price in rows:
            writer.writerow({"Title":"2026 Topps Chrome Player One #10","Sold Price":f"${price}","Shipping":"$0.00","Sold Date":sold_date,"Item ID":str(item_id),"Currency":"USD"})


def test_cli_turns_product_research_export_into_repricing_artifact(tmp_path):
    request_path=tmp_path/"request.json"; asset_path=tmp_path/"asset.json"; csv_path=tmp_path/"research.csv"; output_path=tmp_path/"verification.json"
    request_path.write_text(json.dumps(_request()),encoding="utf-8"); asset_path.write_text(json.dumps(_asset()),encoding="utf-8"); _write_csv(csv_path)
    assert main(["--request",str(request_path),"--asset",str(asset_path),"--csv",str(csv_path),"--output",str(output_path)])==0
    artifact=json.loads(output_path.read_text(encoding="utf-8"))
    assert artifact["schema"]=="opportunity-repricing-collection.v1"
    assert artifact["verification"]["verified"] is True
    assert artifact["verification"]["repricing_pct"]==27.27


def test_cli_fails_closed_when_asset_identity_does_not_match_request(tmp_path):
    request_path=tmp_path/"request.json"; asset_path=tmp_path/"asset.json"; csv_path=tmp_path/"research.csv"
    request_path.write_text(json.dumps(_request()),encoding="utf-8"); asset=_asset(); asset["card_id"]="wrong-card"; asset_path.write_text(json.dumps(asset),encoding="utf-8"); _write_csv(csv_path)
    error=io.StringIO()
    with redirect_stderr(error):
        assert main(["--request",str(request_path),"--asset",str(asset_path),"--csv",str(csv_path)])==2
    assert "asset card_id must match repricing request" in error.getvalue()


def test_cli_rejects_non_object_request_json(tmp_path):
    request_path=tmp_path/"request.json"; asset_path=tmp_path/"asset.json"; csv_path=tmp_path/"research.csv"
    request_path.write_text("[]",encoding="utf-8"); asset_path.write_text(json.dumps(_asset()),encoding="utf-8"); _write_csv(csv_path)
    error=io.StringIO()
    with redirect_stderr(error):
        assert main(["--request",str(request_path),"--asset",str(asset_path),"--csv",str(csv_path)])==2
    assert "request JSON must be an object" in error.getvalue()
