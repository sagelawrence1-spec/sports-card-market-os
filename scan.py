import argparse, json
from data_provider import load_raw_bundle
from feature_engineering import derive_all
from engine import analyze
from memory import ScanMemory

def run_scan(folder,top_n=25,memory_path=None):
    features=derive_all(load_raw_bundle(folder))
    signals=[analyze(x) for x in features]

    priority={"BUY":6,"SELL":6,"ACCUMULATE":5,"TRIM":5,"AVOID":4,"HOLD":2,"WATCH":1}
    signals.sort(key=lambda s:(
        "AOA" in s.alerts,"MIR" in s.alerts,
        priority.get(s.signal,0),s.rar_score,s.mi_score
    ),reverse=True)

    run_id=None
    if memory_path:
        run_id=ScanMemory(memory_path).save(folder,signals)

    high=[s for s in signals if s.signal in ("BUY","SELL") or "AOA" in s.alerts]
    if not high:
        print("NO MATERIAL EDGE DETECTED.")
        return signals

    print("=== SPORTS CARD MARKET OS v0.2 — SCAN ===")
    if run_id: print(f"run_id={run_id}")
    for s in signals[:top_n]:
        tags=",".join(s.alerts) if s.alerts else "-"
        print(
            f"{s.observation_id} | {s.sport} | {s.player} | {s.signal} | "
            f"IR={s.ir_score} RAR={s.rar_score} MI={s.mi_score} CIE={s.cie_score} | "
            f"conf={s.confidence}% | {tags}"
        )
        print(" ",s.thesis)
    return signals

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("folder")
    p.add_argument("--top",type=int,default=25)
    p.add_argument("--memory",default="scan_memory.sqlite")
    a=p.parse_args()
    run_scan(a.folder,a.top,a.memory)
