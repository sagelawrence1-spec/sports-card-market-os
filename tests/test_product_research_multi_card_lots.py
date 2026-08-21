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


def test_rejects_explicit_lot_of_multiple_cards(tmp_path):
    path=tmp_path/"sold.csv"
    _write(path,"2025 Topps Chrome Shohei Ohtani Lot of 3 Cards")

    result=EbayProductResearchProvider().load_csv(path)

    assert result.records==[]
    assert result.metadata["rejected_rows"]==1
    assert result.metadata["rejection_reasons"]=={"multi_card_lot":1}


def test_rejects_numeric_card_lot_even_when_quantity_is_one(tmp_path):
    path=tmp_path/"sold.csv"
    _write(path,"2025 Topps Chrome Shohei Ohtani 2 Card Lot")

    result=EbayProductResearchProvider().load_csv(path)

    assert result.records==[]
    assert result.metadata["rejection_reasons"]=={"multi_card_lot":1}


def test_rejects_explicit_multi_card_bundle(tmp_path):
    path=tmp_path/"sold.csv"
    _write(path,"2025 Topps Chrome Shohei Ohtani Bundle of 4 Cards")

    result=EbayProductResearchProvider().load_csv(path)

    assert result.records==[]
    assert result.metadata["rejection_reasons"]=={"multi_card_lot":1}


def test_rejects_numeric_card_set_even_when_quantity_is_one(tmp_path):
    path=tmp_path/"sold.csv"
    _write(path,"2025 Topps Chrome Shohei Ohtani 3 Card Set")

    result=EbayProductResearchProvider().load_csv(path)

    assert result.records==[]
    assert result.metadata["rejection_reasons"]=={"multi_card_lot":1}


def test_rejects_pair_of_cards_even_when_quantity_is_one(tmp_path):
    path=tmp_path/"sold.csv"
    _write(path,"2025 Topps Chrome Shohei Ohtani Pair of Cards")

    result=EbayProductResearchProvider().load_csv(path)

    assert result.records==[]
    assert result.metadata["rejection_reasons"]=={"multi_card_lot":1}


def test_rejects_spelled_out_multi_card_lot(tmp_path):
    path=tmp_path/"sold.csv"
    _write(path,"2025 Topps Chrome Shohei Ohtani Lot of Three Cards")

    result=EbayProductResearchProvider().load_csv(path)

    assert result.records==[]
    assert result.metadata["rejection_reasons"]=={"multi_card_lot":1}


def test_card_number_does_not_trigger_multi_card_lot_filter(tmp_path):
    path=tmp_path/"sold.csv"
    _write(path,"2025 Topps Chrome Shohei Ohtani Card #2 Refractor")

    result=EbayProductResearchProvider().load_csv(path)

    assert len(result.records)==1
    assert result.metadata["rejected_rows"]==0
