from datetime import date, datetime, timezone

VALID_DIFFICULTIES = {'easy', 'medium', 'hard'}
_LEETCODE_EPOCH = date(2015, 1, 1)  # LeetCode launched 2015; nothing before this is valid

def validate_coding_record(record: dict) -> None:
    """Raises ValueError if the record is invalid."""
    if not record.get('student_id'):
        raise ValueError("student_id is required")
    if not record.get('problem_id'):
        raise ValueError("problem_id is required")
    if record.get('difficulty') not in VALID_DIFFICULTIES:
        raise ValueError(
            f"difficulty must be one of {VALID_DIFFICULTIES}, "
            f"got: {record.get('difficulty')}"
        )
    solved = record.get('solved_at')
    if solved:
        if solved > date.today():
            raise ValueError(f"solved_at cannot be a future date: {solved}")
        if solved < _LEETCODE_EPOCH:
            raise ValueError(
                f"solved_at {solved} is before 2015-01-01 — "
                "unrealistic for any coding platform data"
            )

def validate_github_record(record: dict) -> None:
    """Raises ValueError if the record is invalid."""
    if not record.get('student_id'):
        raise ValueError("student_id is required")
    if not record.get('repo_name'):
        raise ValueError("repo_name is required")
    if not isinstance(record.get('commits'), int) or record['commits'] <= 0:
        raise ValueError(f"commits must be a positive integer")
    cd = record.get('commit_date')
    if cd and cd > date.today():
        raise ValueError(f"commit_date cannot be a future date: {cd}")

# ── Provider observations (Phase 6) ────────────────────────────────────
OBSERVATION_TYPES = {
    "github_public_repo_count", "github_repo_commit_count",
    "leetcode_solved_easy", "leetcode_solved_medium", "leetcode_solved_hard",
}
_REPO_TYPES = {"github_repo_commit_count"}
_MAX_COUNT = 1_000_000
_GITHUB_EPOCH = datetime(2008, 1, 1, tzinfo=timezone.utc)


def validate_observation(o) -> None:
    """Raise ValueError('<rule_code>: detail') if an Observation must not be stored."""
    if o.observation_type not in OBSERVATION_TYPES:
        raise ValueError(f"unknown_type: {o.observation_type!r}")
    v = o.value_num
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v in (float("inf"), float("-inf")):
        raise ValueError("bad_value: not a finite number")
    if v < 0 or v > _MAX_COUNT or v != int(v):
        raise ValueError(f"out_of_range: {v}")
    if o.observation_type in _REPO_TYPES and not (o.source_object_id and len(o.source_object_id) <= 200):
        raise ValueError("bad_source_id: repo name missing or too long")
    if o.granularity not in ("event", "aggregate") or (o.granularity == "aggregate" and o.event_at_precision == "exact"):
        raise ValueError("bad_granularity: an aggregate cannot have an exact event time")
    if o.event_at is not None:
        if o.event_at.tzinfo is None:
            raise ValueError("bad_event_at: timestamp without timezone")
        if o.event_at > datetime.now(timezone.utc):
            raise ValueError("bad_event_at: in the future")
        if o.event_at < _GITHUB_EPOCH:
            raise ValueError("bad_event_at: before 2008")
    elif o.event_at_precision != "unknown":
        raise ValueError("bad_event_at: precision claimed without a timestamp")
