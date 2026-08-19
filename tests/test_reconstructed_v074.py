import csv
from datetime import date, timedelta

from bulk_ingest import ingest_product_research
from entity_matcher import SportsCardEntityMatcher
from evidence_store import EvidenceStore
from market_engine import calibration_metrics, estimate_market, realized_outcome_report
from providers.ebay_product_research import EbayProductResearchProvider

ASSET={"card_id":"ohtani-hmt1","player":"Shohei Ohtani","year":2018,"manufacturer":"Topps",
       "set_name":"Chrome Update","card_number":"HMT1","parallel":"Refractor","autograph":0,
       "grade_company":"PSA","grade":10,"serial_number":""}

def decision(title): return SportsCardEntityMatcher().match(ASSET,title)
def title(suffix=""): return f"2018 Topps Chrome Update Shohei Ohtani HMT1 Refractor PSA 10 {suffix}".strip()

def test_exact_identity_accepts(): assert decision(title()).accepted
def test_wrong_year_rejects(): assert decision(title().replace("2018","2019")).reason=="wrong_year"
def test_wrong_card_number_rejects(): assert decision(title().replace("HMT1","HMT32")).reason=="wrong_card_number"
def test_wrong_grade_rejects(): assert decision(title().replace("PSA 10","PSA 9")).reason=="wrong_grade"
def test_reprint_rejects(): assert decision(title("reprint")).reason.startswith("hard_exclude")
def test_lot_rejects(): assert decision(title("lot of 3 cards")).reason=="multi_card_lot"

def test_parser_preserves_currency_shipping_and_format(tmp_path):
    path=tmp_path/"sold.csv"
    with path.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["Item Title","Sold Price","Sold Date","Item ID","Currency","Shipping","Listing Format"])
        w.writeheader(); w.writerow({"Item Title":title(),"Sold Price":"$3,250.00","Sold Date":"2026-08-01","Item ID":"1","Currency":"usd","Shipping":"$12.50","Listing Format":"Best Offer"})
    record=EbayProductResearchProvider().load_csv(path).records[0]
    assert record.price==3262.5 and record.currency=="USD" and record.payload["normalized_shipping"]==12.5

def sales(prices,currency="USD"):
    today=date(2026,8,12)
    return [{"sale_date":str(today-timedelta(days=i)),"sale_price":p,"currency":currency} for i,p in enumerate(prices)]

def test_estimate_uses_real_sales(): assert estimate_market("x",sales([100,105,110]),"2026-08-12").fair_value > 100
def test_estimate_rejects_future_sales(): assert estimate_market("x",[{"sale_date":"2026-08-13","sale_price":999}],"2026-08-12").sample_size==0
def test_estimate_rejects_non_usd(): assert estimate_market("x",sales([100],"EUR"),"2026-08-12").sample_size==0
def test_estimate_rejects_outlier(): assert estimate_market("x",sales([100,101,99,100,9999]),"2026-08-12").fair_value < 110
def test_estimate_has_evidence_grade(): assert estimate_market("x",sales([100]*12),"2026-08-12").evidence_grade in "ABCDF"
def test_calibration_requires_samples(): assert not calibration_metrics([{"predicted_value":100,"realized_value":110}]).get("calibrated")
def test_calibration_grades_realized_values(): assert calibration_metrics([{"predicted_value":100,"realized_value":110}]*8)["hit_rate"]==1

def write_bulk(path):
    with path.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["Item Title","Sold Price","Shipping","Sold Date","Item ID"]); w.writeheader()
        w.writerow({"Item Title":title(),"Sold Price":"$100","Shipping":"$0.00","Sold Date":"2026-08-01","Item ID":"1"})

def test_bulk_dry_run_does_not_write(tmp_path):
    path=tmp_path/"sold.csv"; write_bulk(path); db=tmp_path/"evidence.sqlite"
    result=ingest_product_research(path,[ASSET],db,dry_run=True)
    assert result["accepted"]==1 and EvidenceStore(db).counts()=={}

def test_bulk_import_is_idempotent(tmp_path):
    path=tmp_path/"sold.csv"; write_bulk(path); db=tmp_path/"evidence.sqlite"
    first=ingest_product_research(path,[ASSET],db,dry_run=False); second=ingest_product_research(path,[ASSET],db,dry_run=False)
    assert first["written"]==1 and second["duplicate"] and second["written"]==0

def outcome(**updates):
    row={"prediction_date":"2026-07-01","realized_date":"2026-08-01","predicted_value":100,
         "realized_value":110,"currency":"USD","evidence_grade":"A"}
    row.update(updates); return row

def test_realized_report_blocks_temporal_leakage():
    report=realized_outcome_report([outcome(realized_date="2026-06-30")],min_samples=1)
    assert report["samples"]==0

def test_realized_report_blocks_non_usd():
    report=realized_outcome_report([outcome(currency="EUR")],min_samples=1)
    assert report["samples"]==0

def test_realized_report_segments_evidence_quality():
    report=realized_outcome_report([outcome(),outcome(evidence_grade="B",realized_value=90)],min_samples=2)
    assert report["calibrated"] and set(report["by_evidence_grade"])=={"A","B"}
