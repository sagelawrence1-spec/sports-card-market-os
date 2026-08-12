import csv
from pathlib import Path
from collections import defaultdict

def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def load_raw_bundle(folder):
    p = Path(folder)
    required = [
        "assets.csv","sales.csv","market_snapshots.csv",
        "population_snapshots.csv","athlete_snapshots.csv",
        "hierarchy_comparables.csv"
    ]
    for name in required:
        if not (p/name).exists():
            raise FileNotFoundError(p/name)

    assets = {r["card_id"]: r for r in read_csv(p/"assets.csv")}
    sales = defaultdict(list)
    for r in read_csv(p/"sales.csv"): sales[r["card_id"]].append(r)
    market = defaultdict(list)
    for r in read_csv(p/"market_snapshots.csv"): market[r["card_id"]].append(r)
    pops = defaultdict(list)
    for r in read_csv(p/"population_snapshots.csv"): pops[r["card_id"]].append(r)
    athlete = {r["player"]: r for r in read_csv(p/"athlete_snapshots.csv")}
    hierarchy = {r["card_id"]: r for r in read_csv(p/"hierarchy_comparables.csv")}
    return assets, sales, market, pops, athlete, hierarchy
