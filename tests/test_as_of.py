from datetime import date, timedelta

from features.as_of import FEATURES_VERSION, activity_trend, features_as_of

T = date(2024, 6, 30)


def series(n, fn=lambda i: 1):
    """n days ending T; i=0 is T."""
    return {T - timedelta(days=i): fn(i) for i in range(n)}


def test_future_days_never_change_features():
    base = series(100, lambda i: i % 3)
    before = features_as_of(base, T)
    leaked = {**base, T + timedelta(days=1): 99, T + timedelta(days=30): 7}
    assert features_as_of(leaked, T) == before


def test_mutating_after_t_is_ignored_but_mutating_before_t_is_not():
    base = series(100)
    mutated = {**base, T + timedelta(days=2): 500}
    assert features_as_of(mutated, T) == features_as_of(base, T)
    assert features_as_of({**base, T: 50}, T)["weekly_counts"][0] == 56


def test_deterministic_and_versioned():
    d = series(90, lambda i: i % 4)
    assert features_as_of(d, T) == features_as_of(dict(reversed(list(d.items()))), T)
    assert features_as_of(d, T)["version"] == FEATURES_VERSION


def test_short_history_is_not_available_not_zero():
    f = features_as_of(series(10), T)
    assert f["weekly_counts"][:1] == [7] and f["weekly_counts"][1] is None  # week 1 has only 3 days
    assert all(w is None for w in f["weekly_counts"][2:])
    assert f["active_days_28d"] is None
    assert f["weeks_since_last_active"] == 0


def test_no_history_is_all_none():
    f = features_as_of({}, T)
    assert f["weekly_counts"] == [None] * 12
    assert f["weeks_since_last_active"] is None and f["active_days_28d"] is None


def test_all_zero_full_history_is_measured_zero():
    f = features_as_of(series(84, lambda i: 0), T)
    assert f["weekly_counts"] == [0] * 12 and f["active_days_28d"] == 0
    assert f["weeks_since_last_active"] is None  # not active anywhere on record


def test_weeks_since_last_active_and_28d():
    d = series(84, lambda i: 1 if i in (15, 16) else 0)
    f = features_as_of(d, T)
    assert f["weeks_since_last_active"] == 2 and f["active_days_28d"] == 2


def test_trend_rule():
    assert activity_trend([1] * 12) == {
        "active_weeks_last_4": 4,
        "active_weeks_prev_8": 8,
        "direction": "flat",
    }
    assert activity_trend([1] * 4 + [0] * 8)["direction"] == "up"
    assert activity_trend([0] * 4 + [1] * 8)["direction"] == "down"
    assert (
        activity_trend([1, 1, None, 1] + [1] * 8)["direction"] is None
    )  # a missing week blocks the rule
    assert activity_trend([1] * 5)["direction"] is None
