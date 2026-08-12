def detect_alerts(f):
    v=f.values
    alerts=[]

    scarcity_trap=(
        v["population"] < 60 and v["demand_score"] < 65 and
        v["liquidity_score"] < 40 and v["social_momentum_index"] < 55
    )
    population_trap=(
        v["population_growth_30d"] > .08 and
        v["listing_growth_30d"] > .25
    )
    breakout=(
        v["sales_velocity"] > 1.10 and v["listing_growth_30d"] < -.20 and
        v["catalyst_score"] > 80 and v["demand_score"] > 70 and
        v["risk_score"] < 48
    )
    grail=(
        v["accepted_grail_substitute_flag"] > .5 and
        v["demand_score"] > 65 and v["risk_score"] < 45
    )
    forced=(
        v["temporary_supply_shock_flag"] > .5 and
        v["market_inefficiency_score"] > 80 and
        v["demand_score"] > 50 and v["risk_score"] < 60
    )
    overheated=(
        v["listing_growth_30d"] > .45 and v["social_momentum_index"] > 85 and
        v["risk_score"] > 68 and v["relative_value_score"] < 50
    )

    if scarcity_trap or population_trap or breakout or grail or forced:
        alerts.append("MIR")

    if population_trap or breakout or overheated or (abs(v["price_change_30d"]) >= .12 and not forced):
        alerts.append("PMD")

    if breakout or grail or forced:
        alerts.append("AOA")

    return alerts
