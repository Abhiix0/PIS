import pytest
from unittest.mock import patch, MagicMock
from ingest.leetcode_api import fetch_leetcode_data, _parse_submission_stats


def _base_mock(counts=None) -> MagicMock:
    """Build a standard mock response using only submitStats."""
    if counts is None:
        counts = [
            {"difficulty": "Easy",   "count": 5},
            {"difficulty": "Medium", "count": 4},
            {"difficulty": "Hard",   "count": 1},
        ]
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {
        "data": {
            "matchedUser": {
                "username": "testuser",
                "submitStats": {"acSubmissionNum": counts},
            }
        }
    }
    return mock


def test_parse_submission_stats_correct():
    stats = [
        {"difficulty": "Easy",   "count": 60},
        {"difficulty": "Medium", "count": 70},
        {"difficulty": "Hard",   "count": 20},
    ]
    result = _parse_submission_stats(stats)
    assert result["easy"]   == 60
    assert result["medium"] == 70
    assert result["hard"]   == 20


def test_fetch_leetcode_data_user_not_found():
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {"data": {"matchedUser": None}}
    with patch("requests.post", return_value=mock):
        with pytest.raises(ValueError, match="not found or profile is private"):
            fetch_leetcode_data("definitely_not_a_real_user_xyz123")


def test_fetch_leetcode_data_returns_records_and_source():
    """fetch_leetcode_data must return (records, 'real_leetcode_stats')."""
    with patch("requests.post", return_value=_base_mock()):
        records, source = fetch_leetcode_data("testuser")

    assert source == "real_leetcode_stats"
    assert len(records) == 10  # 5 easy + 4 medium + 1 hard — exact, never inflated
    assert all(r["difficulty"] in ["easy", "medium", "hard"] for r in records)
    assert all("problem_id" in r for r in records)
    assert all("solved_at" in r for r in records)


def test_total_count_never_exceeds_real_stats():
    """Total records must equal exactly the sum of real LeetCode counts."""
    counts = [
        {"difficulty": "Easy",   "count": 12},
        {"difficulty": "Medium", "count": 0},
        {"difficulty": "Hard",   "count": 0},
    ]
    with patch("requests.post", return_value=_base_mock(counts=counts)):
        records, _ = fetch_leetcode_data("testuser")

    assert len(records) == 12, (
        f"Expected exactly 12 records matching real stats, got {len(records)}"
    )


def test_problem_ids_are_unique():
    """No duplicate problem_ids — ON CONFLICT safety."""
    with patch("requests.post", return_value=_base_mock()):
        records, _ = fetch_leetcode_data("testuser")

    ids = [r["problem_id"] for r in records]
    assert len(ids) == len(set(ids)), "Duplicate problem_ids found"


def test_difficulty_distribution_matches_stats():
    """Records must reflect the exact difficulty counts from submitStats."""
    with patch("requests.post", return_value=_base_mock()):
        records, _ = fetch_leetcode_data("testuser")

    easy_count   = sum(1 for r in records if r["difficulty"] == "easy")
    medium_count = sum(1 for r in records if r["difficulty"] == "medium")
    hard_count   = sum(1 for r in records if r["difficulty"] == "hard")

    assert easy_count   == 5
    assert medium_count == 4
    assert hard_count   == 1


def test_fetch_leetcode_data_no_stats_raises():
    """If submitStats is empty, raise ValueError."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {
        "data": {
            "matchedUser": {
                "username": "testuser",
                "submitStats": {"acSubmissionNum": []},
            }
        }
    }
    with patch("requests.post", return_value=mock):
        with pytest.raises(ValueError, match="no submission stats available"):
            fetch_leetcode_data("testuser")


def test_fetch_leetcode_data_zero_solved_returns_empty():
    """User exists but solved 0 problems — return empty list."""
    mock = _base_mock(counts=[
        {"difficulty": "Easy",   "count": 0},
        {"difficulty": "Medium", "count": 0},
        {"difficulty": "Hard",   "count": 0},
    ])
    with patch("requests.post", return_value=mock):
        records, source = fetch_leetcode_data("testuser")

    assert records == []
    assert source == "real_leetcode_stats"


def test_fetch_leetcode_api_timeout():
    import requests as req_lib
    with patch("requests.post", side_effect=req_lib.exceptions.Timeout):
        with pytest.raises(RuntimeError, match="timed out"):
            fetch_leetcode_data("anyuser")
