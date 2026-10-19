from datetime import UTC, datetime

OBSERVATION_TYPES = {
    "github_public_repo_count",
    "github_repo_commit_count",
    "github_contribution_day",
    "leetcode_solved_easy",
    "leetcode_solved_medium",
    "leetcode_solved_hard",
}
_REPO_TYPES = {"github_repo_commit_count"}
_MAX_COUNT = 1_000_000
_GITHUB_EPOCH = datetime(2008, 1, 1, tzinfo=UTC)


def validate_observation(o) -> None:
    """Raise ValueError('<rule_code>: detail') if an Observation must not be stored."""
    if o.observation_type not in OBSERVATION_TYPES:
        raise ValueError(f"unknown_type: {o.observation_type!r}")
    v = o.value_num
    if (
        isinstance(v, bool)
        or not isinstance(v, (int, float))
        or v != v
        or v in (float("inf"), float("-inf"))
    ):
        raise ValueError("bad_value: not a finite number")
    if v < 0 or v > _MAX_COUNT or v != int(v):
        raise ValueError(f"out_of_range: {v}")
    if o.observation_type in _REPO_TYPES and not (
        o.source_object_id and len(o.source_object_id) <= 200
    ):
        raise ValueError("bad_source_id: repo name missing or too long")
    if o.granularity not in ("event", "aggregate") or (
        o.granularity == "aggregate" and o.event_at_precision == "exact"
    ):
        raise ValueError("bad_granularity: an aggregate cannot have an exact event time")
    if o.event_at is not None:
        if o.event_at.tzinfo is None:
            raise ValueError("bad_event_at: timestamp without timezone")
        if o.event_at > datetime.now(UTC):
            raise ValueError("bad_event_at: in the future")
        if o.event_at < _GITHUB_EPOCH:
            raise ValueError("bad_event_at: before 2008")
    elif o.event_at_precision != "unknown":
        raise ValueError("bad_event_at: precision claimed without a timestamp")
    if o.observation_type == "github_contribution_day" and not (
        o.granularity == "event"
        and o.event_at_precision == "day"
        and o.source_object_id == o.event_at.date().isoformat()
    ):
        raise ValueError(
            "bad_source_id: day observation needs event granularity, day precision, date id"
        )
