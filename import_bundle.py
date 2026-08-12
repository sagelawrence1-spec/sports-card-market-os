import argparse
from warehouse import Warehouse
from adapters.csv_bundle import CSVBundleAdapter

def run(folder,db):
    a=CSVBundleAdapter(folder); w=Warehouse(db)
    w.upsert_assets(a.assets(),a.name)
    w.insert_sales(a.sales(),a.name)
    w.insert_market(a.market_snapshots(),a.name)
    w.insert_pops(a.population_snapshots(),a.name)
    w.insert_athletes(a.athlete_snapshots(),a.name)
    w.insert_hierarchy(a.hierarchy_comparables(),a.name)
    print(w.counts())

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('folder'); p.add_argument('db'); a=p.parse_args(); run(a.folder,a.db)
