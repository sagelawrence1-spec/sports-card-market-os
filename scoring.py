def clamp(x,lo=0,hi=100): return max(lo,min(hi,x))

def score(f):
    v=f.values
    # IR: upside/market opportunity
    ir=clamp(
        .18*v["relative_value_score"] + .18*v["market_inefficiency_score"] +
        .15*v["catalyst_score"] + .13*v["demand_score"] +
        .12*v["card_quality_score"] + .08*v["scarcity_score"] +
        .08*v["cultural_score"] + .08*v["performance_percentile"]
    )

    # RAR: opportunity discounted by risk and poor execution.
    rar=clamp(
        ir - .34*v["risk_score"] + .18*v["liquidity_score"] +
        min(max(v["sales_velocity"]-1, -1),1.5)*5
    )

    # MI is a direct derived anomaly score.
    mi=clamp(v["market_inefficiency_score"])

    # CIE balances investability with collector quality.
    cie=clamp(
        .28*rar + .20*v["card_quality_score"] + .15*v["cultural_score"] +
        .13*v["scarcity_score"] + .12*v["demand_score"] + .12*v["liquidity_score"]
    )
    return round(ir,1),round(rar,1),round(mi,1),round(cie,1)
