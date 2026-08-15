import csv

from providers.ebay_product_research import EbayProductResearchProvider


def _write(path, rows):
    fields=["Item Title","Sold Price","Shipping","Sold Date","Item ID","Currency"]
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def test_duplicate_item_id_with_same_landed_total_but_different_components_fails_closed(tmp_path):
    path=tmp_path/"sold.csv"
    base={
        "Item Title":"2018 Topps Chrome Update Shohei Ohtani HMT1 PSA 10",
        "Sold Date":"2026-08-01",
        "Item ID":"123456789012",
        "Currency":"USD",
    }
    _write(path,[
        {**base,"Sold Price":"$100.00","Shipping":"$10.00"},
        {**base,"Sold Price":"$105.00","Shipping":"$5.00"},
    ])

    result=EbayProductResearchProvider().load_csv(path)

    assert result.records==[]
    assert result.metadata["accepted_rows"]==0
    assert result.metadata["deduplicated_rows"]==0
    assert result.metadata["rejected_rows"]==2
    assert result.metadata["rejection_reasons"]=={"conflicting_duplicate_evidence":2}


def test_duplicate_item_id_with_identical_price_components_still_deduplicates(tmp_path):
    path=tmp_path/"sold.csv"
    row={
        "Item Title":"2018 Topps Chrome Update Shohei Ohtani HMT1 PSA 10",
        "Sold Price":"$100.00",
        "Shipping":"$10.00",
        "Sold Date":"2026-08-01",
        "Item ID":"123456789012",
        "Currency":"USD",
    }
    _write(path,[row,row.copy()])

    result=EbayProductResearchProvider().load_csv(path)

    assert len(result.records)==1
    assert result.records[0].price==110.0
    assert result.metadata["accepted_rows"]==1
    assert result.metadata["deduplicated_rows"]==1
    assert result.metadata["rejected_rows"]==0
