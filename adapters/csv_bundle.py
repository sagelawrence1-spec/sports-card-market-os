import csv
from pathlib import Path
from .base import SourceAdapter

class CSVBundleAdapter(SourceAdapter):
    name="csv_bundle"
    def __init__(self, folder): self.folder=Path(folder)
    def _read(self,name):
        p=self.folder/name
        if not p.exists(): return []
        with p.open(newline='',encoding='utf-8') as f: return list(csv.DictReader(f))
    def assets(self): return self._read('assets.csv')
    def sales(self): return self._read('sales.csv')
    def market_snapshots(self): return self._read('market_snapshots.csv')
    def population_snapshots(self): return self._read('population_snapshots.csv')
    def athlete_snapshots(self): return self._read('athlete_snapshots.csv')
    def hierarchy_comparables(self): return self._read('hierarchy_comparables.csv')
