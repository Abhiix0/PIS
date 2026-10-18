"""DB-free checks for validation rules, the feature dictionary, and removal of the fabricated-data paths."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from features.compute import FEATURE_SCHEMA_VERSION, SCALE_COLS
from ingest.provider import Observation
from ingest.validators import validate_observation

ROOT = Path(__file__).resolve().parent.parent
PUSHED = datetime(2024, 3, 1, tzinfo=UTC)


def commit_obs(**kw):
    base = dict(
        provider="github",
        observation_type="github_repo_commit_count",
        value_num=3,
        source_object_id="r",
        event_at=PUSHED,
        event_at_precision="repo_push",
    )
    return Observation(**{**base, **kw})


def test_valid_observations_pass():
    validate_observation(commit_obs())
    validate_observation(Observation("leetcode", "leetcode_solved_easy", 0))


@pytest.mark.parametrize(
    "kw,rule",
    [
        (dict(observation_type="nope"), "unknown_type"),
        (dict(value_num=-1), "out_of_range"),
        (dict(value_num=2_000_000), "out_of_range"),
        (dict(value_num=1.5), "out_of_range"),
        (dict(value_num=float("nan")), "bad_value"),
        (dict(value_num=float("inf")), "bad_value"),
        (dict(value_num="7"), "bad_value"),
        (dict(value_num=True), "bad_value"),
        (dict(source_object_id=None), "bad_source_id"),
        (dict(source_object_id="x" * 201), "bad_source_id"),
        (dict(event_at_precision="exact"), "bad_granularity"),
        (dict(event_at=datetime.now(UTC) + timedelta(days=1)), "bad_event_at"),
        (dict(event_at=datetime(2001, 1, 1, tzinfo=UTC)), "bad_event_at"),
        (dict(event_at=datetime(2024, 1, 1)), "bad_event_at"),
        (dict(event_at=None), "bad_event_at"),
    ],
)
def test_invalid_observations_raise_with_a_rule_code(kw, rule):
    with pytest.raises(ValueError) as e:
        validate_observation(commit_obs(**kw))
    assert str(e.value).split(":")[0] == rule


def test_every_scaled_feature_is_in_the_data_dictionary():
    doc = (ROOT / "docs" / "data-dictionary" / "features.md").read_text(encoding="utf-8")
    assert FEATURE_SCHEMA_VERSION in doc
    for col in SCALE_COLS:
        assert f"| `{col}` |" in doc, col


def test_no_code_path_invents_leetcode_rows_or_dates():
    for rel in ("ingest/leetcode_api.py", "services/pipeline.py", "app/routers/ingest.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert not re.search(r"\brandom\b|SYNTHETIC_WEIGHT|REAL_WEIGHT|fetch_leetcode_data", src), (
            rel
        )
