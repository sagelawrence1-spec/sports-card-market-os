"""eBay active-listing adapter.

Browse API is appropriate for current listing/supply snapshots. Sold-history retrieval
is intentionally separate because eBay Marketplace Insights is restricted/limited-release.
"""
import os, requests

class EbayBrowseClient:
    BASE='https://api.ebay.com/buy/browse/v1'
    def __init__(self, app_token=None, marketplace='EBAY_US'):
        self.token=app_token or os.getenv('EBAY_APP_TOKEN')
        self.marketplace=marketplace
    def search(self, query, limit=50, offset=0):
        if not self.token: raise RuntimeError('Set EBAY_APP_TOKEN')
        headers={'Authorization':f'Bearer {self.token}','X-EBAY-C-MARKETPLACE-ID':self.marketplace}
        params={'q':query,'limit':limit,'offset':offset}
        r=requests.get(f'{self.BASE}/item_summary/search',headers=headers,params=params,timeout=30)
        r.raise_for_status(); return r.json()
