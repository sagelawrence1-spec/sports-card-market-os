from reconstruction import summarize_reconstruction_health


def market_state(card_id, *, has_previous=True, unexplained=False, hard_failure=False):
    return {
        "card_id": card_id,
        "reconstruction": {
            "has_previous": has_previous,
            "unexplained_repricing": unexplained,
            "reconstruction_health_failure": hard_failure,
        },
    }


def test_universe_health_is_healthy_for_clean_states():
    summary = summarize_reconstruction_health([
        market_state("CARD-A"),
        market_state("CARD-B"),
        market_state("CARD-C", has_previous=False),
    ])

    assert summary["status"] == "healthy"
    assert summary["total_cards"] == 3
    assert summary["cards_with_previous"] == 2
    assert summary["initial_observations"] == 1
    assert summary["cards_requiring_review"] == []


def test_universe_health_degrades_for_non_hard_unexplained_repricing():
    summary = summarize_reconstruction_health([
        market_state("CARD-A"),
        market_state("CARD-B", unexplained=True),
    ])

    assert summary["status"] == "degraded"
    assert summary["unexplained_repricing_count"] == 1
    assert summary["hard_failure_count"] == 0
    assert summary["unexplained_repricing_rate"] == 0.5
    assert summary["cards_requiring_review"] == ["CARD-B"]


def test_any_hard_failure_fails_closed_and_surfaces_cards():
    summary = summarize_reconstruction_health([
        market_state("CARD-C", unexplained=True, hard_failure=True),
        market_state("CARD-A", unexplained=True),
        market_state("CARD-B"),
    ])

    assert summary["status"] == "failed"
    assert summary["unexplained_repricing_count"] == 2
    assert summary["hard_failure_count"] == 1
    assert summary["cards_requiring_review"] == ["CARD-A", "CARD-C"]
    assert summary["hard_failure_cards"] == ["CARD-C"]


def test_initial_observations_do_not_dilute_reconstruction_failure_rates():
    summary = summarize_reconstruction_health([
        market_state("CARD-A", has_previous=False),
        market_state("CARD-B", has_previous=True, unexplained=True),
    ])

    assert summary["cards_with_previous"] == 1
    assert summary["unexplained_repricing_rate"] == 1.0


def test_empty_universe_is_healthy_and_zeroed():
    summary = summarize_reconstruction_health([])

    assert summary["status"] == "healthy"
    assert summary["total_cards"] == 0
    assert summary["cards_with_previous"] == 0
    assert summary["unexplained_repricing_rate"] == 0.0
    assert summary["hard_failure_rate"] == 0.0
