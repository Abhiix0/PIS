"""Point-in-time features from daily activity counts: only days <= t are read, so later data cannot leak in.

A day absent from `daily_counts` is unknown, never zero. A value that needs an unknown day is None ("not available").
"""

from datetime import date, timedelta

FEATURES_VERSION = "as-of-v1"
WEEKS = 12


def features_as_of(daily_counts: dict[date, int], t: date) -> dict:
    """weekly_counts[0] is the 7 days ending t, [1] the 7 before that, ... 12 weeks. None = a day was missing.
    weeks_since_last_active: whole weeks since the last day with count > 0 (None if no active day on record).
    active_days_28d: days with count > 0 in the 28 days ending t (None if any of those days is missing)."""
    day = lambda back: daily_counts.get(t - timedelta(days=back))  # noqa: E731  (back=0 is t itself)
    weekly = []
    for w in range(WEEKS):
        days = [day(7 * w + i) for i in range(7)]
        weekly.append(None if None in days else sum(days))  # type: ignore[arg-type]
    active = [t - d for d in daily_counts if d <= t and daily_counts[d] > 0]
    last28 = [day(i) for i in range(28)]
    return {
        "version": FEATURES_VERSION,
        "as_of": t.isoformat(),
        "weekly_counts": weekly,
        "weeks_since_last_active": min(active).days // 7 if active else None,
        "active_days_28d": None if None in last28 else sum(c > 0 for c in last28 if c is not None),
    }


def activity_trend(weekly_counts: list[int | None]) -> dict:
    """Rule: active weeks (count > 0) in the last 4 weeks vs the 8 before. Needs all 12 weeks, else direction None.
    Direction compares per-week rates: last4/4 vs prev8/8."""
    recent, prior = weekly_counts[:4], weekly_counts[4:12]
    if len(weekly_counts) < 12 or None in recent or None in prior:
        return {"active_weeks_last_4": None, "active_weeks_prev_8": None, "direction": None}
    a, b = sum(c > 0 for c in recent), sum(c > 0 for c in prior)  # type: ignore[operator]
    return {
        "active_weeks_last_4": a,
        "active_weeks_prev_8": b,
        "direction": "up" if 2 * a > b else "down" if 2 * a < b else "flat",
    }
