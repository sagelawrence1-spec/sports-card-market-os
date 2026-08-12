from datetime import date
import math, statistics
from models import DerivedFeatures

AS_OF = date(2026,8,11)

def f(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))

def mean(xs):
    return sum(xs)/len(xs) if xs else 0.0

def safe_pct(a,b):
    return (a/b)-1 if b else 0.0

def _sales_window(rows, days):
    out=[]
    for r in rows:
        try:
            d=date.fromisoformat(r["sale_date"])
            if 0 <= (AS_OF-d).days <= days:
                out.append(r)
        except Exception:
            pass
    return out

def _latest_before(rows, days):
    cutoff = AS_OF.toordinal()-days
    valid=[]
    for r in rows:
        try:
            d=date.fromisoformat(r["snapshot_date"])
            valid.append((abs(d.toordinal()-cutoff), d, r))
        except Exception:
            pass
    return min(valid, key=lambda x:x[0])[2] if valid else None

def derive_all(bundle):
    assets,sales_map,market_map,pops_map,athlete_map,hierarchy_map=bundle
    out=[]
    for cid,a in assets.items():
        sales=sales_map[cid]
        s7=_sales_window(sales,7); s30=_sales_window(sales,30); s90=_sales_window(sales,90)
        p7=mean([f(x["sale_price"]) for x in s7])
        p30=mean([f(x["sale_price"]) for x in s30])
        p90=mean([f(x["sale_price"]) for x in s90])
        prices30=[f(x["sale_price"]) for x in s30]
        vol30=(statistics.pstdev(prices30)/p30) if len(prices30)>1 and p30 else 0.0
        buyers30=len(set(x.get("buyer_id_hash","") for x in s30 if x.get("buyer_id_hash","")))
        velocity=(len(s30)/(len(s90)/3)) if len(s90) else 0.0

        mrows=market_map[cid]
        m0=_latest_before(mrows,0); m30=_latest_before(mrows,30)
        listings=f(m0["active_listings"]) if m0 else 0
        listings30=f(m30["active_listings"]) if m30 else listings
        listing_growth=safe_pct(listings,listings30)
        median_ask=f(m0["median_ask"]) if m0 else 0
        spread=safe_pct(median_ask,p30) if p30 else 0

        prows=pops_map[cid]
        pop0=_latest_before(prows,0); pop30r=_latest_before(prows,30); pop90r=_latest_before(prows,90)
        pop=f(pop0["population"]) if pop0 else 0
        pop30=f(pop30r["population"]) if pop30r else pop
        pop90=f(pop90r["population"]) if pop90r else pop
        pop_growth30=safe_pct(pop,pop30)
        pop_growth90=safe_pct(pop,pop90)

        ar=athlete_map.get(a["player"],{})
        hr=hierarchy_map.get(cid,{})
        perf=f(ar.get("performance_percentile"))
        trend=f(ar.get("season_trend_percentile"))
        search=f(ar.get("collector_search_index"))
        media=f(ar.get("media_attention_index"))
        social=f(ar.get("social_momentum_index"))
        event=f(ar.get("event_probability_index"))
        injury=f(ar.get("injury_risk_index"))
        role=f(ar.get("role_change_flag"))
        supply_shock=f(ar.get("temporary_supply_shock_flag"))

        rookie=f(a.get("rookie_flag"))
        auto=f(a.get("autograph"))
        grade=f(a.get("grade"))
        tier_rank=f(a.get("tier_rank"),7)
        serial=f(a.get("serial_number"),0)
        substitute=f(hr.get("accepted_grail_substitute_flag"))
        superior_now=f(hr.get("superior_tier_market_value_current"))
        superior_90=f(hr.get("superior_tier_market_value_90d"))
        peer_now=f(hr.get("peer_cohort_index_value_current"))
        peer90=f(hr.get("peer_cohort_index_value_90d"))

        move7=safe_pct(p7,p30)
        move30=safe_pct(p30,p90)
        peer_discount=safe_pct(peer_now,p30) if p30 else 0
        superior_move=safe_pct(superior_now,superior_90)
        sales_per_listing=(len(s30)/max(1,listings))
        unique_buyer_ratio=buyers30/max(1,len(s30))

        # Derived primitives
        liquidity = clamp(
            35 + min(len(s30),30)*1.1 + min(buyers30,20)*0.7 +
            min(sales_per_listing,3)*6 - max(spread,0)*45 - vol30*35
        )

        demand = clamp(
            .28*search + .18*media + .16*social +
            min(velocity,2.5)*12 + min(unique_buyer_ratio,1)*12 -
            max(listing_growth,0)*12
        )

        # Metadata-driven card quality
        card_quality = clamp(
            45 + rookie*12 + auto*10 + max(0,8-tier_rank)*4 +
            (8 if grade>=10 else 3) + (8 if serial and serial<=99 else 0)
        )

        # Effective scarcity: low population helps only modestly; serial helps more.
        scarcity = clamp(
            35 + (28/(1+math.log10(max(pop,1)))) +
            (22 if serial and serial<=99 else 0) +
            (7 if serial and serial<=199 else 0) -
            max(pop_growth90,0)*45
        )

        catalyst = clamp(.45*event + .25*perf + .15*trend + role*15 - injury*.12)

        cultural = clamp(.58*media + .27*search + .15*social)

        # Relative value comes from peer cohort and hierarchy behavior, not a supplied score.
        relative_value = clamp(
            50 + peer_discount*85 +
            substitute*10 +
            max(superior_move-.20,0)*24 -
            max(move30-.20,0)*50
        )

        # Market inefficiency is anomaly based.
        bullish_mi = (
            max(velocity-1,0)*18 +
            max(-listing_growth,0)*24 +
            max(peer_discount,0)*50 +
            substitute*max(superior_move-.20,0)*28 +
            supply_shock*max(-move30,0)*55
        )
        bearish_mi = (
            max(pop_growth30-.05,0)*130 +
            max(listing_growth-.15,0)*35 +
            max(move30-.20,0)*25 +
            max(social-85,0)*.6
        )
        no_demand_scarcity = max(0, scarcity-75)*max(0,45-demand)/40
        mi = clamp(40 + bullish_mi + bearish_mi + no_demand_scarcity)

        risk = clamp(
            20 + vol30*95 + max(spread,0)*55 +
            max(pop_growth30,0)*65 + max(listing_growth,0)*25 +
            injury*.18 + max(45-demand,0)*.5
        )

        vals={
            "avg_price_7d":p7,"avg_price_30d":p30,"avg_price_90d":p90,
            "sales_7d":len(s7),"sales_30d":len(s30),"sales_90d":len(s90),
            "unique_buyers_30d":buyers30,"sales_velocity":velocity,
            "volatility_30d":vol30,"active_listings":listings,
            "listing_growth_30d":listing_growth,"bid_ask_spread_pct":spread,
            "population":pop,"population_growth_30d":pop_growth30,"population_growth_90d":pop_growth90,
            "price_change_7d":move7,"price_change_30d":move30,
            "peer_discount_pct":peer_discount,"superior_tier_move_90d":superior_move,
            "liquidity_score":liquidity,"demand_score":demand,"card_quality_score":card_quality,
            "scarcity_score":scarcity,"catalyst_score":catalyst,"cultural_score":cultural,
            "relative_value_score":relative_value,"market_inefficiency_score":mi,"risk_score":risk,
            "performance_percentile":perf,"social_momentum_index":social,
            "accepted_grail_substitute_flag":substitute,
            "temporary_supply_shock_flag":supply_shock,
        }
        out.append(DerivedFeatures(
            card_id=cid,observation_id=a["observation_id"],player=a["player"],sport=a["sport"],
            values=vals,context={"asset":a,"athlete":ar,"hierarchy":hr}
        ))
    return out
