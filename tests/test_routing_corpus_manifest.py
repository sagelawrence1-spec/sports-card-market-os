import pytest

from routing_corpus_manifest import CorpusManifestPolicy, build_routing_corpus_manifest


def _card(index, *, player=None, sport=None):
    return {
        "card_id": f"CARD-{index:03d}",
        "player": player or f"Player {index}",
        "sport": sport or ("Baseball" if index % 2 else "Basketball"),
    }


def test_manifest_is_deterministic_and_unique():
    cards = [_card(i) for i in range(40)]
    policy = CorpusManifestPolicy(target_size=25, max_sport_share=0.60)
    first = build_routing_corpus_manifest(cards, policy=policy, seed="fixed")
    second = build_routing_corpus_manifest(list(reversed(cards)), policy=policy, seed="fixed")
    assert first["cards"] == second["cards"]
    assert first["distinct_cards"] == 25
    assert len({row["card_id"] for row in first["cards"]}) == 25


def test_player_concentration_is_bounded():
    cards = [
        _card(i, player="Shohei Ohtani" if i < 10 else f"Player {i}")
        for i in range(40)
    ]
    policy = CorpusManifestPolicy(target_size=25, max_per_player=2, max_sport_share=0.60)
    manifest = build_routing_corpus_manifest(cards, policy=policy)
    assert sum(row["player"] == "Shohei Ohtani" for row in manifest["cards"]) <= 2
    assert manifest["largest_player_count"] <= 2


def test_sport_concentration_is_bounded():
    cards = [
        _card(i, sport="Baseball" if i < 30 else "Basketball")
        for i in range(50)
    ]
    policy = CorpusManifestPolicy(target_size=20, max_sport_share=0.60)
    manifest = build_routing_corpus_manifest(cards, policy=policy)
    assert manifest["largest_sport_share"] <= 0.60
    assert manifest["distinct_sports"] >= 2


def test_undersized_pool_fails_closed():
    with pytest.raises(RuntimeError, match="eligible pool too small"):
        build_routing_corpus_manifest(
            [_card(i) for i in range(10)],
            policy=CorpusManifestPolicy(target_size=25),
        )


def test_concentrated_pool_that_cannot_satisfy_caps_fails_closed():
    cards = [_card(i, player="One Player") for i in range(30)]
    with pytest.raises(RuntimeError, match="concentration constraints"):
        build_routing_corpus_manifest(
            cards,
            policy=CorpusManifestPolicy(target_size=25, max_per_player=2, max_sport_share=1.0),
        )


def test_missing_identity_rows_are_not_silently_counted():
    cards = [_card(i) for i in range(25)] + [{"card_id": "BROKEN", "player": "", "sport": "Baseball"}]
    manifest = build_routing_corpus_manifest(
        cards,
        policy=CorpusManifestPolicy(target_size=25, max_sport_share=0.60),
    )
    assert all(row["card_id"] != "BROKEN" for row in manifest["cards"])
