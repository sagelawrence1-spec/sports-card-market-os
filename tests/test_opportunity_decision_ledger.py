import copy

import pytest

from opportunity_decision_ledger import OpportunityDecisionLedger, decision_packet_id


def _packet():
    return {
        "schema": "opportunity-decision-packet.v1",
        "player_id": "player-1",
        "player": "Player One",
        "sport": "baseball",
        "headline": "Player One call-up creates a hobby catalyst",
        "signal_kind": "CALL_UP",
        "catalyst_at": "2026-08-10T12:00:00+00:00",
        "as_of": "2026-08-18T10:00:00+00:00",
        "why_now": "Attention can outrun repricing after the promotion.",
        "thesis": "The first Bowman remains attractive if sold comps have not materially repriced.",
        "falsification": ["Role disappears", "Market reprices beyond chase threshold"],
        "source_urls": ["https://example.com/player-one"],
        "card": {"card_id": "card-10", "label": "2026 Bowman Chrome Player One #10"},
        "pricing": {
            "verified": True,
            "repricing_pct": 8.0,
            "blocking_reason": None,
            "evidence_ids": ["EBAY_PRODUCT_RESEARCH:1", "EBAY_PRODUCT_RESEARCH:2"],
        },
        "decision": "START_POSITION",
        "actionable": True,
        "stage": "ENTRY",
        "engine_action": "BUY",
        "edge_conviction": 88.0,
        "evidence_confidence": 84.0,
    }


def test_persists_and_reads_exact_packet(tmp_path):
    ledger = OpportunityDecisionLedger(tmp_path / "opportunities.sqlite")
    packet = _packet()
    packet_id = ledger.persist_packet(packet)

    assert packet_id == decision_packet_id(packet)
    assert ledger.get_packet(packet_id) == packet
    assert ledger.list_packets() == (packet,)


def test_exact_retry_is_idempotent(tmp_path):
    ledger = OpportunityDecisionLedger(tmp_path / "opportunities.sqlite")
    packet = _packet()
    first = ledger.persist_packet(packet)
    second = ledger.persist_packet(copy.deepcopy(packet))

    assert first == second
    assert len(ledger.list_packets()) == 1


def test_same_decision_moment_cannot_be_rewritten_with_hindsight(tmp_path):
    ledger = OpportunityDecisionLedger(tmp_path / "opportunities.sqlite")
    packet = _packet()
    ledger.persist_packet(packet)

    revised = copy.deepcopy(packet)
    revised["decision"] = "DO_NOT_CHASE"
    revised["actionable"] = False
    revised["pricing"]["repricing_pct"] = 40.0

    with pytest.raises(ValueError, match="immutable"):
        ledger.persist_packet(revised)


def test_later_as_of_allows_a_new_decision_snapshot(tmp_path):
    ledger = OpportunityDecisionLedger(tmp_path / "opportunities.sqlite")
    first = _packet()
    ledger.persist_packet(first)

    later = copy.deepcopy(first)
    later["as_of"] = "2026-08-20T10:00:00+00:00"
    later["decision"] = "DO_NOT_CHASE"
    later["actionable"] = False
    later["pricing"]["repricing_pct"] = 40.0
    ledger.persist_packet(later)

    assert ledger.list_packets() == (first, later)


def test_rejects_unsupported_or_incomplete_packets(tmp_path):
    ledger = OpportunityDecisionLedger(tmp_path / "opportunities.sqlite")
    packet = _packet()
    packet["schema"] = "future.v2"
    with pytest.raises(ValueError, match="unsupported"):
        ledger.persist_packet(packet)

    packet = _packet()
    packet["card"] = {}
    with pytest.raises(ValueError, match="requires"):
        ledger.persist_packet(packet)
