from models import Signal
from scoring import score
from detectors import detect_alerts

def classify(f,ir,rar,mi,cie):
    v=f.values

    scarcity_trap=(
        v["population"] < 60 and v["demand_score"] < 65 and
        v["liquidity_score"] < 40 and v["social_momentum_index"] < 55
    )
    if scarcity_trap:
        return "AVOID"

    if v["population_growth_30d"] > .08 and v["listing_growth_30d"] > .25 and v["risk_score"] > 53:
        return "SELL"

    if (
        v["listing_growth_30d"] > .45 and v["social_momentum_index"] > 85 and
        v["risk_score"] > 68 and v["relative_value_score"] < 50
    ):
        return "TRIM"

    if (
        v["temporary_supply_shock_flag"] > .5 and
        v["market_inefficiency_score"] > 80 and
        v["demand_score"] > 50 and v["catalyst_score"] > 58 and v["risk_score"] < 60
    ):
        return "BUY"

    if (
        v["sales_velocity"] > 1.10 and v["listing_growth_30d"] < -.20 and
        v["catalyst_score"] > 80 and v["demand_score"] > 70 and v["risk_score"] < 48
    ):
        return "BUY"

    if (
        v["accepted_grail_substitute_flag"] > .5 and
        v["demand_score"] > 65 and v["risk_score"] < 45
    ):
        return "ACCUMULATE"

    if cie >= 60 and v["risk_score"] < 32.4 and v["market_inefficiency_score"] < 75:
        return "HOLD"

    return "WATCH"

def thesis(f,signal):
    v=f.values
    if signal=="AVOID":
        return "Low population is not translating into buyer depth or liquidity; rarity alone is not investability."
    if signal=="SELL":
        return "Graded population and available listings are expanding faster than buyer absorption, creating latent downside."
    if signal=="TRIM":
        return "Listings, risk, and social momentum indicate an overheated move whose price has outrun relative value."
    if signal=="BUY":
        if v["temporary_supply_shock_flag"]:
            return "A temporary supply shock created a dislocation while underlying demand, catalyst strength, and execution remain intact."
        return "Sales velocity is accelerating while listings contract; athlete/catalyst data confirm the premium market is moving before supply adjusts."
    if signal=="ACCUMULATE":
        return "The superior grail tier is repricing faster than an accepted substitute, creating a grail-compression setup."
    if signal=="HOLD":
        return "The asset retains strong collector quality and execution characteristics, but current pricing offers no material inefficiency."
    return "Mixed raw-market evidence does not justify decisive capital allocation."

def confidence(f,signal):
    v=f.values
    base=48 + min(v["sales_30d"],25)*.7 + min(v["unique_buyers_30d"],20)*.5
    base += max(v["liquidity_score"]-50,0)*.18
    base -= max(v["bid_ask_spread_pct"]-.15,0)*35
    if signal in ("WATCH","HOLD"): base-=3
    return round(max(35,min(91,base)),1)

def analyze(f):
    ir,rar,mi,cie=score(f)
    signal=classify(f,ir,rar,mi,cie)
    alerts=detect_alerts(f)
    return Signal(
        observation_id=f.observation_id,card_id=f.card_id,player=f.player,sport=f.sport,
        signal=signal,confidence=confidence(f,signal),ir_score=ir,rar_score=rar,mi_score=mi,cie_score=cie,
        alerts=alerts,thesis=thesis(f,signal),diagnostics=f.values
    )
