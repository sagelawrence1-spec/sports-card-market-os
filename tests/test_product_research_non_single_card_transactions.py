import csv

from providers.ebay_product_research import EbayProductResearchProvider


def _write(path, title):
    fields=["Item Title","Sold Price","Shipping","Sold Date","Item ID","Currency","Quantity"]
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        writer.writerow({
            "Item Title":title,
            "Sold Price":"$100.00",
            "Shipping":"$5.00",
            "Sold Date":"2026-08-19",
            "Item ID":"123456789012",
            "Currency":"USD",
            "Quantity":"1",
        })


def _assert_rejected(tmp_path, title):
    path=tmp_path/"sold.csv"
    _write(path,title)
    result=EbayProductResearchProvider().load_csv(path)
    assert result.records==[]
    assert result.metadata["rejection_reasons"]=={"non_single_card_transaction":1}


def test_rejects_repack_transaction(tmp_path):
    _assert_rejected(tmp_path,"2025 Topps Chrome Shohei Ohtani Refractor Repack")


def test_rejects_mystery_pack_transaction(tmp_path):
    _assert_rejected(tmp_path,"2025 Topps Chrome Shohei Ohtani Mystery Pack")


def test_rejects_break_spot_transaction(tmp_path):
    _assert_rejected(tmp_path,"2025 Topps Chrome Shohei Ohtani Player Break Spot")


def test_rejects_pick_your_team_transaction(tmp_path):
    _assert_rejected(tmp_path,"2025 Topps Chrome Pick Your Team Shohei Ohtani")


def test_breakout_insert_does_not_trigger_break_filter(tmp_path):
    path=tmp_path/"sold.csv"
    _write(path,"2025 Topps Chrome Shohei Ohtani Breakout Insert Card #2")
    result=EbayProductResearchProvider().load_csv(path)
    assert len(result.records)==1
    assert result.metadata["rejected_rows"]==0


def test_standard_single_card_comp_remains_accepted(tmp_path):
    path=tmp_path/"sold.csv"
    _write(path,"2025 Topps Chrome Shohei Ohtani Refractor Card #2")
    result=EbayProductResearchProvider().load_csv(path)
    assert len(result.records)==1
    assert result.metadata["rejected_rows"]==0
