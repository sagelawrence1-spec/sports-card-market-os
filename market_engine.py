from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
import math
import statistics

@dataclass(frozen=True)
class MarketEstimate:
    card_id: str
    as_of: str
    fair_value: float | None
    sample_size: int
    effective_sample_size: float
    dispersion: float | None
    confidence: float
    evidence_grade: str

def _day(value):
    if isinstance(value,date): return value
    return datetime.fromisoformat(str(value)[:10]).date()

def valuation_sample(sales,as_of=None,currency="USD"):
    """Return the exact evidence rows that survive the valuation filters."""
    cutoff=_day(as_of or date.today())
    clean=[]
    for row in sales:
        if str(row.get("currency","USD")).upper()!=currency: continue
        sold=_day(row["sale_date"])
        if sold > cutoff: continue
        price=float(row["sale_price"])
        if price <= 0: continue
        clean.append((sold,price,row))
    if not clean:
        return []
    prices=[price for _,price,_ in clean]
    median=statistics.median(prices)
    deviations=[abs(p-median) for p in prices]
    mad=statistics.median(deviations) if len(prices)>1 else 0
    if mad:
        clean=[entry for entry in clean if abs(entry[1]-median)/(1.4826*mad) <= 3.5]
    elif len(prices) >= 4:
        # MAD collapses to zero when a majority of comps share the exact same price.
        # Do not let one extreme contamination row disable outlier filtering entirely.
        median_count=sum(1 for price in prices if price == median)
        if median > 0 and median_count >= (len(prices)+1)//2:
            clean=[entry for entry in clean if (median/3) <= entry[1] <= (median*3)]
    return [row for _,_,row in clean]

def estimate_market(card_id, sales, as_of=None, half_life_days=45, currency="USD"):
    cutoff=_day(as_of or date.today())
    sample=valuation_sample(sales,cutoff,currency)
    if not sample:
        return MarketEstimate(card_id,cutoff.isoformat(),None,0,0,None,0,"F")
    clean=[(_day(row["sale_date"]),float(row["sale_price"])) for row in sample]
    weighted=[]
    for sold,price in clean:
        weight=.5 ** ((cutoff-sold).days/half_life_days)
        weighted.append((price,weight))
    fair=sum(p*w for p,w in weighted)/sum(w for _,w in weighted)
    ess=sum(w for _,w in weighted)**2/sum(w*w for _,w in weighted)
    dispersion=(statistics.pstdev([p for p,_ in weighted])/fair) if len(weighted)>1 and fair else 0
    confidence=max(0,min(100,18+min(ess,12)*5.2-max(0,dispersion-.08)*85))
    newest_age=min((cutoff-sold).days for sold,_ in clean)
    confidence-=min(40,max(0,newest_age-30)*.5)
    confidence=max(0,confidence)
    grade="A" if confidence>=80 else "B" if confidence>=65 else "C" if confidence>=50 else "D" if confidence>=35 else "F"
    return MarketEstimate(card_id,cutoff.isoformat(),round(fair,2),len(weighted),round(ess,2),round(dispersion,4),round(confidence,1),grade)

def calibration_metrics(predictions, min_samples=8):
    graded=[]
    for p in predictions:
        predicted=float(p["predicted_value"]); realized=float(p["realized_value"])
        if predicted>0: graded.append((realized-predicted)/predicted)
    if len(graded)<min_samples:
        return {"calibrated":False,"samples":len(graded),"reason":"insufficient_samples"}
    return {"calibrated":True,"samples":len(graded),"mean_return":round(statistics.mean(graded),4),
            "median_return":round(statistics.median(graded),4),"hit_rate":round(sum(x>0 for x in graded)/len(graded),4)}

def realized_outcome_report(predictions, min_samples=8):
    """Grade estimates only when the realized sale occurs after the prediction."""
    valid=[]
    for row in predictions:
        if str(row.get("currency","USD")).upper() != "USD": continue
        if _day(row["realized_date"]) <= _day(row["prediction_date"]): continue
        predicted=float(row["predicted_value"]); realized=float(row["realized_value"])
        if predicted <= 0 or realized <= 0: continue
        error=(realized-predicted)/predicted
        valid.append({"grade":row.get("evidence_grade","unknown"),"error":error})
    overall=calibration_metrics([
        {"predicted_value":1,"realized_value":1+x["error"]} for x in valid
    ],min_samples=min_samples)
    buckets={}
    for grade in sorted({x["grade"] for x in valid}):
        errors=[x["error"] for x in valid if x["grade"]==grade]
        buckets[grade]={"samples":len(errors),"mape":round(statistics.mean(abs(x) for x in errors),4),
                        "bias":round(statistics.mean(errors),4)}
    overall["by_evidence_grade"]=buckets
    return overall
