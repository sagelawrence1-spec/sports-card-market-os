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
    fields=['Item Title','Sold Price','Sold Date','Item ID','Item URL','Currency','Shipping']
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        w.writerow({'Item Title':'2018 Topps Chrome Update Shohei Ohtani HMT1 Refractor PSA 10','Sold Price':'$3,250.00','Sold Date':'08/01/2026','Item ID':'991','Item URL':'https://www.ebay.com/itm/991','Shipping':'$12.50'})
        w.writerow({'Item Title':'URL identity comp','Sold Price':'$250.00','Sold Date':'2026-08-02','Item URL':'https://www.ebay.com/itm/example-card/996?hash=abc','Shipping':'Free'})
        w.writerow({'Item Title':'Bad date comp','Sold Price':'$100.00','Sold Date':'eventually','Item ID':'992','Shipping':'$0.00'})
        w.writerow({'Item Title':'No currency evidence','Sold Price':'100.00','Sold Date':'2026-08-02','Item ID':'993','Shipping':'$0.00'})
        w.writerow({'Item Title':'Canadian comp','Sold Price':'125.00','Sold Date':'2026-08-03','Item ID':'994','Currency':'CAD','Shipping':'$0.00'})
        w.writerow({'Item Title':'Price range comp','Sold Price':'$100-$150','Sold Date':'2026-08-04','Item ID':'995','Shipping':'$0.00'})
        w.writerow({'Item Title':'Missing stable identity','Sold Price':'$175.00','Sold Date':'2026-08-05','Shipping':'$0.00'})
        w.writerow({'Item Title':'Conflicting identity','Sold Price':'$180.00','Sold Date':'2026-08-06','Item ID':'997','Item URL':'https://www.ebay.com/itm/998','Shipping':'$0.00'})
        w.writerow({'Item Title':'   ','Sold Price':'$190.00','Sold Date':'2026-08-07','Item ID':'999','Shipping':'$0.00'})
        w.writerow({'Item Title':'Unknown shipping comp','Sold Price':'$200.00','Sold Date':'2026-08-08','Item ID':'1000','Shipping':''})
        w.writerow({'Item Title':'Qualified foreign dollar comp','Sold Price':'NZD $210.00','Sold Date':'2026-08-09','Item ID':'1001','Shipping':'$0.00'})
    rr=EbayProductResearchProvider().load_csv(str(p),'ohtani')
    assert len(rr.records)==2
    assert rr.records[0].price==3262.5 and rr.records[0].source_item_id=='991'
    assert rr.records[0].payload['normalized_sold_price']==3250.0
    assert rr.records[0].payload['normalized_shipping']==12.5
    assert rr.records[0].payload['price_basis']=='sold_price_plus_shipping'
    assert rr.records[0].event_date=='2026-08-01' and rr.records[0].currency=='USD'
    assert rr.records[1].source_item_id=='996' and rr.records[1].price==250.0
    assert rr.metadata['price_basis']=='sold_price_plus_shipping'
    assert rr.metadata['accepted_rows']==2 and rr.metadata['rejected_rows']==9
    assert rr.metadata['rejection_reasons']=={
        'conflicting_item_id':1,
        'invalid_or_ambiguous_price':1,
        'invalid_or_missing_shipping':1,
        'invalid_sold_date':1,
        'missing_currency':2,
        'missing_stable_item_id':1,
        'missing_title':1,
        'non_usd_currency':1,
    }
print('adapter tests: PASS')