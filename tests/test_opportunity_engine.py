from opportunity_contract import build_opportunity_radar
from opportunity_engine import (
    OpportunityAction,
    OpportunityEngine,
    OpportunityStage,
    OpportunityStore,
    PlayerSignal,
    SignalType,
    advance_stage,
    score_opportunity_factors,
)


def test_edge_can_be_high_before_evidence_is_mature():
    scores = score_opportunity_factors(
        {
            "situation_change": 85,
            "narrative_potential": 90,
            "collectibility": 85,
            "hobby_lag": 95,
            "attention_velocity": 65,
            "evidence_maturity": 20,
            "upside_asymmetry": 90,
        }
    )
    assert scores.edge_conviction > 80
    assert scores.evidence_confidence < 50


def test_lifecycle_never_moves_backward():
    assert advance_stage(OpportunityStage.ACCELERATION, OpportunityStage.ENTRY) == OpportunityStage.ACCELERATION
    assert advance_stage(OpportunityStage.ENTRY, OpportunityStage.ACCELERATION) == OpportunityStage.ACCELERATION


def test_signing_spark_enters_entry_stage_and_is_journaled(tmp_path):
    store = OpportunityStore(tmp_path / "opportunity.sqlite")
    engine = OpportunityEngine(store)
    thesis = engine.spark(
        player="Example Player",
        sport="MLB",
        observation="Signed into a materially better opportunity.",
        signal_type=SignalType.SIGNING,
        factors={
            "situation_change": 90,
            "narrative_potential": 80,
            "collectibility": 78,
            "hobby_lag": 90,
            "attention_velocity": 50,
            "evidence_maturity": 35,
            "upside_asymmetry": 85,
        },
    )
    assert thesis.stage == OpportunityStage.ENTRY
    assert thesis.recommended_action == OpportunityAction.START_POSITION
    assert len(store.ledger(thesis.thesis_id)) == 1
    assert len(store.signals(thesis.thesis_id)) == 1


def test_first_major_event_advances_entry_to_acceleration(tmp_path):
    store = OpportunityStore(tmp_path / "opportunity.sqlite")
    engine = OpportunityEngine(store)
    thesis = engine.spark(
        player="Example Player",
        sport="MLB",
        observation="Signed.",
        signal_type=SignalType.SIGNING,
        factors={
            "situation_change": 90,
            "narrative_potential": 82,
            "collectibility": 80,
            "hobby_lag": 92,
            "attention_velocity": 40,
            "evidence_maturity": 35,
            "upside_asymmetry": 88,
        },
    )
    updated = engine.apply_signal(
        thesis.thesis_id,
        PlayerSignal(
            player_id=thesis.player_id,
            player=thesis.player,
            sport=thesis.sport,
            signal_type=SignalType.FIRST_MAJOR_EVENT,
            source="game_feed",
            description="First home run.",
            importance=85,
            potential_market_impact=85,
        ),
        factors={
            "situation_change": 88,
            "narrative_potential": 90,
            "collectibility": 82,
            "hobby_lag": 90,
            "attention_velocity": 78,
            "evidence_maturity": 55,
            "upside_asymmetry": 88,
        },
        market_repricing_pct=8,
    )
    assert updated.stage == OpportunityStage.ACCELERATION
    assert updated.recommended_action == OpportunityAction.ADD
    assert len(store.ledger(thesis.thesis_id)) == 2


def test_large_repricing_prevents_chasing(tmp_path):
    store = OpportunityStore(tmp_path / "opportunity.sqlite")
    engine = OpportunityEngine(store)
    thesis = engine.spark(
        player="Example Player",
        sport="MLB",
        observation="Breakout underway.",
        signal_type=SignalType.PERFORMANCE_SPIKE,
        factors={
            "situation_change": 95,
            "narrative_potential": 95,
            "collectibility": 90,
            "hobby_lag": 30,
            "attention_velocity": 95,
            "evidence_maturity": 80,
            "upside_asymmetry": 85,
        },
        market_repricing_pct=70,
    )
    assert thesis.stage == OpportunityStage.ACCELERATION
    assert thesis.recommended_action == OpportunityAction.DO_NOT_CHASE


def test_consensus_and_broken_have_explicit_actions(tmp_path):
    store = OpportunityStore(tmp_path / "opportunity.sqlite")
    engine = OpportunityEngine(store)
    thesis = engine.spark(player="Example", sport="NBA", observation="Something changed.")
    consensus = engine.mark_consensus(thesis.thesis_id, "Narrative is now broadly priced.")
    assert consensus.recommended_action == OpportunityAction.DO_NOT_CHASE
    broken = engine.break_thesis(thesis.thesis_id, "Core premise failed.")
    assert broken.stage == OpportunityStage.BROKEN
    assert broken.recommended_action == OpportunityAction.EXIT


def test_radar_prioritizes_entry_before_consensus(tmp_path):
    store = OpportunityStore(tmp_path / "opportunity.sqlite")
    engine = OpportunityEngine(store)
    entry = engine.spark(
        player="Entry Player",
        sport="MLB",
        observation="Signed.",
        signal_type=SignalType.SIGNING,
    )
    consensus = engine.spark(
        player="Consensus Player",
        sport="MLB",
        observation="Spike.",
        signal_type=SignalType.PERFORMANCE_SPIKE,
    )
    consensus = engine.mark_consensus(consensus.thesis_id, "Everyone sees it now.")
    radar = build_opportunity_radar([consensus, entry])
    assert radar["schema_version"] == "opportunity-radar.v1"
    assert radar["items"][0]["player"] == "Entry Player"


def test_murakami_acceptance_path_signing_then_first_homer(tmp_path):
    store = OpportunityStore(tmp_path / "opportunity.sqlite")
    engine = OpportunityEngine(store)
    signing = engine.spark(
        player="Munetaka Murakami",
        sport="MLB",
        observation="Major-league signing creates a concrete entry catalyst before breakout confirmation.",
        signal_type=SignalType.SIGNING,
        factors={
            "situation_change": 92,
            "narrative_potential": 88,
            "collectibility": 86,
            "hobby_lag": 94,
            "attention_velocity": 48,
            "evidence_maturity": 38,
            "upside_asymmetry": 90,
        },
    )
    assert signing.stage == OpportunityStage.ENTRY
    assert signing.recommended_action == OpportunityAction.START_POSITION

    first_homer = engine.apply_signal(
        signing.thesis_id,
        PlayerSignal(
            player_id=signing.player_id,
            player=signing.player,
            sport=signing.sport,
            signal_type=SignalType.FIRST_MAJOR_EVENT,
            source="game_feed",
            description="First home run confirms part of the thesis while repricing remains limited.",
            importance=88,
            potential_market_impact=92,
        ),
        factors={
            "situation_change": 92,
            "narrative_potential": 94,
            "collectibility": 88,
            "hobby_lag": 91,
            "attention_velocity": 82,
            "evidence_maturity": 58,
            "upside_asymmetry": 90,
        },
        market_repricing_pct=9,
    )
    assert first_homer.stage == OpportunityStage.ACCELERATION
    assert first_homer.recommended_action == OpportunityAction.ADD


def test_westbrook_acceptance_retirement_risk_can_surface_before_retirement(tmp_path):
    store = OpportunityStore(tmp_path / "opportunity.sqlite")
    engine = OpportunityEngine(store)
    thesis = engine.spark(
        player="Russell Westbrook",
        sport="NBA",
        observation="Late-career uncertainty raises retirement-catalyst probability before an announcement.",
        signal_type=SignalType.RETIREMENT_RISK,
        factors={
            "situation_change": 78,
            "narrative_potential": 90,
            "collectibility": 92,
            "hobby_lag": 84,
            "attention_velocity": 42,
            "evidence_maturity": 45,
            "upside_asymmetry": 82,
        },
    )
    assert thesis.stage == OpportunityStage.ENTRY
    assert thesis.opportunity_type.value == "EDGE"
    assert thesis.edge_conviction > thesis.evidence_confidence
    assert thesis.recommended_action == OpportunityAction.START_POSITION
