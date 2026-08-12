import csv,argparse
from data_provider import load_raw_bundle
from feature_engineering import derive_all
from engine import analyze

def aset(s): return set(x for x in (s or "").split("|") if x)

def grade(folder,key_path):
    with open(key_path,newline="",encoding="utf-8") as f:
        key={r["observation_id"]:r for r in csv.DictReader(f)}
    sigs=[analyze(x) for x in derive_all(load_raw_bundle(folder))]
    exact=tp=fp=fn=hs_tp=hs_fp=0
    confusion={}; misses=[]
    for s in sigs:
        k=key[s.observation_id]; exp=k["expected_signal"]
        exact += int(s.signal==exp)
        confusion[(exp,s.signal)]=confusion.get((exp,s.signal),0)+1
        if s.signal!=exp: misses.append((s.observation_id,k["scenario_id"],exp,s.signal,s.ir_score,s.rar_score,s.mi_score,s.cie_score))
        ea=aset(k["expected_alert_types"]); pa=set(s.alerts)
        tp+=len(ea&pa); fp+=len(pa-ea); fn+=len(ea-pa)
        eh=k["expected_high_signal"]=="1"; ph=(s.signal in ("BUY","SELL") or "AOA" in pa)
        hs_tp+=int(eh and ph); hs_fp+=int((not eh) and ph)
    n=len(sigs); p=tp/(tp+fp) if tp+fp else 0; r=tp/(tp+fn) if tp+fn else 0
    f1=2*p*r/(p+r) if p+r else 0; hp=hs_tp/(hs_tp+hs_fp) if hs_tp+hs_fp else 0
    print(f"Rows: {n}")
    print(f"Signal exact match: {exact/n:.1%}")
    print(f"Alert precision: {p:.1%}")
    print(f"Alert recall: {r:.1%}")
    print(f"Alert F1: {f1:.1%}")
    print(f"High-signal precision: {hp:.1%}")
    print(f"Misses: {len(misses)}")
    print("\\nConfusion:")
    for (e,pred),c in sorted(confusion.items()):
        print(f"  {e:10s} -> {pred:10s}: {c}")
    print("\\nFirst 25 misses:")
    for m in misses[:25]: print(" ",m)
    return {"rows":n,"signal_accuracy":exact/n,"alert_precision":p,"alert_recall":r,"alert_f1":f1,"high_signal_precision":hp,"misses":len(misses)}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("folder"); p.add_argument("key")
    a=p.parse_args(); grade(a.folder,a.key)
