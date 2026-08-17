from opportunity_engine import (
    CardExpression,
    OpportunityAction,
    OpportunityEngine,
    OpportunityStage,
    Signal,
    SignalKind,
    ThesisType,
    score_factors,
)


def factors(**overrides):
    base = {
        "situation_change": 90,
        "narrative_potential": 88,
        "collectibility": 86,
        "hobby_lag": 94,
        "attention_velocity": 48,
        "evidence_maturity": 38,
        "upside_asymmetry": 90,
    }
    base.update(overrides)
    return base


def signal(kind, player_id="murakami", description="Observed change"):
    return Signal(player_id, "Munetaka Murakami", "MLB", kind, description, "test")


def test_weak_signal_edge_can_precede_mature_evidence():
    evidence, edge, asymmetry = score_factors(factors())
    assert edge > evidence
    assert edge > 80
    assert asymmetry == 90


def test_call_up_watch_is_catalyst_thesis_before_catalyst_occurs():
    engine = OpportunityEngine()
    thesis = engine.spark(
        player_id="pecko",
        player="Ethan Pecko",
        sport="MLB",
        signal=Signal("pecko", "Ethan Pecko", "MLB", SignalKind.CALL_UP_WATCH, "Scratched while club discusses possible MLB start", "news"),
        headline="Possible call-up is visible before the transaction",
        why_now="Rotation uncertainty and a scratched Triple-A start create a credible near-term catalyst.",
        thesis="The market may not fully price a debut until the roster move is official.",
        falsification=["No call-up", "Rotation spot closes"],
        factors=factors(evidence_maturity=44, attention_velocity=35),
    )
    assert thesis.thesis_type == ThesisType.CATALYST
    assert thesis.stage == OpportunityStage.PRE_CATALYST


def test_signing_creates_entry_catalyst_and_timestamped_ledger():
    engine = OpportunityEngine()
    thesis = engine.spark(
        player_id="murakami",
        player="Munetaka Murakami",
        sport="MLB",
        signal=signal(SignalKind.SIGNING, description="MLB signing creates entry window"),
        headline="Signing creates a pre-breakout entry window",
        why_now="Situation changed before broad hobby repricing.",
        thesis="Attention should accelerate faster than card prices.",
        falsification=["No meaningful playing time", "Cards reprice before confirmation"],
        factors=factors(),
        cards=[CardExpression("murakami-rookie", "Murakami flagship rookie", buy_below=100)],
    )
    assert thesis.thesis_type == ThesisType.CATALYST
    assert thesis.stage == OpportunityStage.ENTRY
    assert thesis.action == OpportunityAction.START_POSITION
    assert thesis.cards[0].buy_below == 100
    assert len(engine.ledger(thesis.thesis_id)) == 1


def test_first_major_performance_advances_entry_to_acceleration():
    engine = OpportunityEngine()
    thesis = engine.spark(
        player_id="murakami", player="Munetaka Murakami", sport="MLB",
        signal=signal(SignalKind.SIGNING), headline="Entry", why_now="Signing",
        thesis="Lag remains", falsification=["No role"], factors=factors(),
    )
    updated = engine.apply_signal(
        thesis.thesis_id,
        signal(SignalKind.PERFORMANCE, description="First major MLB performance"),
        factors=factors(attention_velocity=82, evidence_maturity=58),
        market_repricing_pct=9,
    )
    assert updated.stage == OpportunityStage.ACCELERATION
    assert updated.action == OpportunityAction.ADD
    assert len(engine.ledger(thesis.thesis_id)) == 2


def test_lifecycle_does_not_move_backward():
    engine = OpportunityEngine()
    thesis = engine.spark(
        player_id="murakami", player="Munetaka Murakami", sport="MLB",
        signal=signal(SignalKind.PERFORMANCE), headline="Accel", why_now="Performance",
        thesis="Momentum", falsification=["Regression"], factors=factors(attention_velocity=85),
    )
    updated = engine.apply_signal(thesis.thesis_id, signal(SignalKind.SIGNING), factors=factors())
    assert updated.stage == OpportunityStage.ACCELERATION


def test_large_repricing_blocks_chasing_even_with_strong_edge():
    engine = OpportunityEngine()
    thesis = engine.spark(
        player_id="murakami", player="Munetaka Murakami", sport="MLB",
        signal=signal(SignalKind.PERFORMANCE), headline="Late", why_now="Attention spike",
        thesis="Momentum", falsification=["Reversal"], factors=factors(attention_velocity=95),
        market_repricing_pct=50,
    )
    assert thesis.action == OpportunityAction.DO_NOT_CHASE


def test_quant_signal_is_distinct_from_catalyst_and_edge():
    engine = OpportunityEngine()
    thesis = engine.spark(
        player_id="x", player="Player X", sport="NBA",
        signal=Signal("x", "Player X", "NBA", SignalKind.SALES_VELOCITY, "Volume rising before price", "market"),
        headline="Velocity divergence", why_now="Sales accelerate", thesis="Price may lag",
        falsification=["Velocity fades"], factors=factors(),
    )
    assert thesis.thesis_type == ThesisType.QUANT


def test_consensus_and_broken_have_explicit_non_entry_actions():
    engine = OpportunityEngine()
    thesis = engine.spark(
        player_id="x", player="Player X", sport="NBA",
        signal=Signal("x", "Player X", "NBA", SignalKind.USER_SPARK, "Idea", "user"),
        headline="Idea", why_now="Spark", thesis="Test", falsification=["Invalid"], factors=factors(),
    )
    consensus = engine.mark_consensus(thesis.thesis_id, "Hobby fully repriced")
    assert consensus.action == OpportunityAction.DO_NOT_CHASE
    broken = engine.break_thesis(thesis.thesis_id, "Core premise failed")
    assert broken.action == OpportunityAction.EXIT


def test_radar_prioritizes_entry_over_consensus():
    engine = OpportunityEngine()
    entry = engine.spark(
        player_id="entry", player="Entry", sport="MLB",
        signal=Signal("entry", "Entry", "MLB", SignalKind.SIGNING, "Signed", "news"),
        headline="Entry", why_now="Now", thesis="Lag", falsification=["No role"], factors=factors(),
    )
    late = engine.spark(
        player_id="late", player="Late", sport="MLB",
        signal=Signal("late", "Late", "MLB", SignalKind.PERFORMANCE, "Breakout", "game"),
        headline="Late", why_now="Now", thesis="Momentum", falsification=["Reversal"], factors=factors(),
    )
    engine.mark_consensus(late.thesis_id, "Fully priced")
    assert engine.radar()[0].thesis_id == entry.thesis_id


def test_cross_player_signal_fails_closed():
    engine = OpportunityEngine()
    thesis = engine.spark(
        player_id="x", player="X", sport="MLB",
        signal=Signal("x", "X", "MLB", SignalKind.USER_SPARK, "Idea", "user"),
        headline="X", why_now="Now", thesis="T", falsification=["F"], factors=factors(),
    )
    try:
        engine.apply_signal(thesis.thesis_id, Signal("y", "Y", "MLB", SignalKind.PERFORMANCE, "Wrong player", "game"), factors=factors())
    except ValueError:
        pass
    else:
        raise AssertionError("cross-player signal must fail closed")
