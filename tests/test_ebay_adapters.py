import sys,csv,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from providers.ebay_browse import EbayBrowseProvider
from providers.ebay_product_research import EbayProductResearchProvider

fixture={
  "total":2,"limit":50,"offset":0,
  "itemSummaries":[
    {"itemId":"v1|123|0","legacyItemId":"123","title":"2023 Panini Prizm Victor Wembanyama #136 Silver PSA 10","price":{"value":"1425.00","currency":"USD"},"itemWebUrl":"https://www.ebay.com/itm/123","itemCreationDate":"2026-08-10T00:00:00.000Z"},
    {"itemId":"v1|124|0","legacyItemId":"124","title":"2023 Panini Prizm Victor Wembanyama #136 Base PSA 10","price":{"value":"250.00","currency":"USD"},"itemWebUrl":"https://www.ebay.com/itm/124"}
  ]
}
obj=object.__new__(EbayBrowseProvider); obj.provider_name='ebay_browse'
r=obj._parse_response(fixture,'wemby')
assert len(r.records)==2 and r.records[0].source_item_id=='123' and r.records[0].price==1425.0

with tempfile.TemporaryDirectory() as td:
    p=Path(td)/'research.csv'
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['Item Title','Sold Price','Sold Date','Item ID','Item URL'])
        w.writeheader();w.writerow({'Item Title':'2018 Topps Chrome Update Shohei Ohtani HMT1 Refractor PSA 10','Sold Price':'$3,250.00','Sold Date':'2026-08-01','Item ID':'991','Item URL':'https://www.ebay.com/itm/991'})
    rr=EbayProductResearchProvider().load_csv(str(p),'ohtani')
    assert len(rr.records)==1 and rr.records[0].price==3250.0 and rr.records[0].source_item_id=='991'
print('adapter tests: PASS')
