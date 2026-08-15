import csv

from providers.ebay_product_research import EbayProductResearchProvider


def _write(path, rows):
    fields=["Item Title","Sold Price","Sold Date","Item ID","Currency"]
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def test_identical_duplicate_item_ids_collapse_without_double_weighting(tmp_path):
    path=tmp_path/"sold.csv"
    row={"Item Title":"2018 Topps Chrome Update Shohei Ohtani HMT1 PSA 10","Sold Price":"$100","Sold Date":"2026-08-01","Item ID":"123","Currency":"USD"}
    _write(path,[row,row.copy()])
    result=EbayProductResearchProvider().load_csv(path)
    assert len(result.records)==1
    assert result.metadata["accepted_rows"]==1
    assert result.metadata["deduplicated_rows"]==1
    assert result.metadata["rejected_rows"]==0


def test_conflicting_duplicate_item_ids_fail_closed(tmp_path):
    path=tmp_path/"sold.csv"
    _write(path,[
        {"Item Title":"2018 Topps Chrome Update Shohei Ohtani HMT1 PSA 10","Sold Price":"$100","Sold Date":"2026-08-01","Item ID":"123","Currency":"USD"},
        {"Item Title":"2018 Topps Chrome Update Shohei Ohtani HMT1 PSA 10","Sold Price":"$140","Sold Date":"2026-08-01","Item ID":"123","Currency":"USD"},
    ])
    result=EbayProductResearchProvider().load_csv(path)
    assert result.records==[]
    assert result.metadata["accepted_rows"]==0
    assert result.metadata["deduplicated_rows"]==0
    assert result.metadata["rejected_rows"]==2
    assert result.metadata["rejection_reasons"]=={"conflicting_duplicate_evidence":2}
