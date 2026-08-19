from opportunity_radar import evaluate_live_observation, scan_live_observations


def _payload(*, kind="CALL_UP", source_urls=None, player_id="mlb-test-prospect"):
    return {
        "player_id": player_id,
        "player": "Test Prospect",
        "sport": "MLB",
        "signal_kind": kind,
        "signal_description": "Test catalyst",
        "observed_at": "2026-08-18T20:00:00+00:00",
        "headline": "Test opportunity",
        "why_now": "A fresh catalyst created a potentially mispriced window.",
        "thesis": "The market may not have fully repriced the catalyst yet.",
        "falsification": ["The catalyst is not confirmed."],
        "factors": {
            "situation_change": 90,
            "narrative_potential": 90,
            "collectibility": 90,
            "hobby_lag": 90,
            "attention_velocity": 90,
            "evidence_maturity": 90,
            "upside_asymmetry": 90,
        },
        "market_price_verified": True,
        "market_repricing_pct": 5.0,
        "source_urls": source_urls or ["https://rumor.example.com/test-prospect-call-up"],
        "cards": [
            {
                "card_id": "test-card",
                "label": "Test Card",
                "priority": 1,
                "rationale": "Test expression",
            }
        ],
    }


def test_single_unconfirmed_event_source_cannot_unlock_capital():
    candidate = evaluate_live_observation(_payload())

    assert candidate.market_price_verified is True
    assert candidate.decision == "WATCH"
    assert candidate.blocking_reason == "catalyst_source_unconfirmed"
    assert candidate.source_quality == "SINGLE_SOURCE"
    assert candidate.source_host_count == 1


def test_two_independent_event_sources_can_unlock_capital():
    candidate = evaluate_live_observation(
        _payload(
            source_urls=[
                "https://report-one.example.com/test-prospect-call-up",
                "https://report-two.example.net/test-prospect-call-up",
            ]
        )
    )

    assert candidate.decision == "START_POSITION"
    assert candidate.blocking_reason is None
    assert candidate.source_quality == "CORROBORATED"
    assert candidate.source_host_count == 2


def test_single_official_league_source_can_unlock_capital():
    candidate = evaluate_live_observation(
        _payload(source_urls=["https://www.mlb.com/news/test-prospect-called-up"])
    )

    assert candidate.decision == "START_POSITION"
    assert candidate.blocking_reason is None
    assert candidate.source_quality == "OFFICIAL"
    assert candidate.source_host_count == 1


def test_single_source_performance_edge_is_not_over_gated():
    candidate = evaluate_live_observation(
        _payload(kind="PERFORMANCE", source_urls=["https://local-report.example.com/test-prospect-breakout"])
    )

    assert candidate.decision == "ADD"
    assert candidate.blocking_reason is None
    assert candidate.source_quality == "SINGLE_SOURCE"


def test_source_quality_is_only_a_ranking_tiebreaker():
    single = _payload(
        kind="PERFORMANCE",
        player_id="single-source",
        source_urls=["https://local-report.example.com/breakout"],
    )
    official = _payload(
        kind="PERFORMANCE",
        player_id="official-source",
        source_urls=["https://www.mlb.com/news/breakout"],
    )

    report = scan_live_observations([single, official])

    assert [candidate.thesis.player_id for candidate in report.candidates] == [
        "official-source",
        "single-source",
    ]
    assert [candidate.source_quality for candidate in report.candidates] == [
        "OFFICIAL",
        "SINGLE_SOURCE",
    ]


def test_repeated_urls_from_same_host_do_not_fake_corroboration():
    candidate = evaluate_live_observation(
        _payload(
            source_urls=[
                "https://report.example.com/one",
                "https://www.report.example.com/two",
            ]
        )
    )

    assert candidate.source_quality == "SINGLE_SOURCE"
    assert candidate.source_host_count == 1
    assert candidate.decision == "WATCH"
    assert candidate.blocking_reason == "catalyst_source_unconfirmed"
