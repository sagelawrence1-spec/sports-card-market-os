"""PSA adapter boundary.

PSA's current public API documents cert verification access. Population Report data is
publicly viewable on PSA, but this adapter intentionally does not scrape it. A licensed
or explicitly supported population endpoint can be wired here if/when available.
"""
import os, requests

class PSAClient:
    BASE='https://api.psacard.com/publicapi'
    def __init__(self, bearer_token=None):
        self.token=bearer_token or os.getenv('PSA_BEARER_TOKEN')
    def cert_by_number(self, cert_number):
        if not self.token:
            raise RuntimeError('Set PSA_BEARER_TOKEN')
        r=requests.get(f'{self.BASE}/cert/GetByCertNumber/{cert_number}',headers={'Authorization':f'bearer {self.token}'},timeout=30)
        r.raise_for_status(); return r.json()
