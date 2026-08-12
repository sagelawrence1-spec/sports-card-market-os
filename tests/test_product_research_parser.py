import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from providers.ebay_product_research import EbayProductResearchProvider


def test_tsv_product_research_parse(tmp_path):
    text = (
        'Item Title\tSold Price\tSold Date\tItem ID\tShipping Cost\tFormat\n'
        '2023 Panini Prizm Victor Wembanyama #136 Silver PSA 10\t$1,234.56\tAug 10, 2026\t123\t$5.00\tBest Offer\n'
    )
    p = tmp_path / 'x.tsv'
    p.write_text(text, encoding='utf-8')
    r = EbayProductResearchProvider().load_csv(str(p), 'q')
    assert len(r.records) == 1
    x = r.records[0]
    assert x.price == 1234.56
    assert x.event_date == '2026-08-10'
    assert x.payload['_parsed_shipping'] == 5.0
    assert x.payload['_selling_format'] == 'Best Offer'


def test_missing_item_id_gets_stable_synthetic_identity(tmp_path):
    text = (
        'Item Title,Sold Price,Sold Date,Currency\n'
        '2023 Panini Prizm Victor Wembanyama #136 Silver PSA 10,$999.99,Aug 9 2026,USD\n'
    )
    p = tmp_path / 'a.csv'
    p.write_text(text, encoding='utf-8')
    r1 = EbayProductResearchProvider().load_csv(str(p), 'q').records[0]
    r2 = EbayProductResearchProvider().load_csv(str(p), 'q').records[0]
    assert r1.source_item_id == r2.source_item_id
    assert r1.source_item_id.startswith('synthetic-')


def test_ambiguous_price_range_is_rejected(tmp_path):
    text = 'Item Title,Sold Price,Sold Date\nCard,$100 - $120,Aug 9 2026\n'
    p = tmp_path / 'range.csv'
    p.write_text(text, encoding='utf-8')
    assert EbayProductResearchProvider().load_csv(str(p), 'q').records == []
