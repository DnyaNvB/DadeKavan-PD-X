from workers.worker_a import normalize_best_limits


def test_normalize_best_limits_preserves_previous_values():
    state = {}
    levels, _ = normalize_best_limits(
        [{"number": 1, "pMeDem": 100, "qTitMeDem": 10, "zOrdMeDem": 2, "pMeOf": 110, "qTitMeOf": 20, "zOrdMeOf": 3}],
        state,
    )
    assert levels[0].bid_price == 100
    levels, _ = normalize_best_limits([{"number": 1, "pMeDem": 101}], state)
    assert levels[0].bid_price == 101
    assert levels[0].ask_price == 110
