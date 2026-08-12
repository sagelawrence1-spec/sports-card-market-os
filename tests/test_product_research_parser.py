import sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from providers.ebay_product_research import EbayProductResearchProvider

text='Item Title\tSold Price\tSold Date\tItem ID\tShipping Cost\tFormat\n2023 Panini Prizm Victor Wembanyama #136 Silver PSA 10\t$1,234.56\tAug 10, 2026\t123\t$5.00\tBest Offer\n'
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/'x.tsv'; p.write_text(text,encoding='utf-8')
    r=EbayProductResearchProvider().load_csv(str(p),'q')
    assert len(r.records)==1
    x=r.records[0]
    assert x.price==1234.56 and x.event_date=='2026-08-10' and x.payload['_parsed_shipping']==5.0 and x.payload['_selling_format']=='Best Offer'

text='Item Title,Sold Price,Sold Date,Currency\n2023 Panini Prizm Victor Wembanyama #136 Silver PSA 10,$999.99,Aug 9 2026,USD\n'
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/'a.csv'; p.write_text(text,encoding='utf-8')
    r1=EbayProductResearchProvider().load_csv(str(p),'q').records[0]
    r2=EbayProductResearchProvider().load_csv(str(p),'q').records[0]
    assert r1.source_item_id==r2.source_item_id and r1.source_item_id.startswith('synthetic-')

text='Item Title,Sold Price,Sold Date\nCard,$100 - $120,Aug 9 2026\n'
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/'range.csv'; p.write_text(text,encoding='utf-8')
    assert EbayProductResearchProvider().load_csv(str(p),'q').records==[]
