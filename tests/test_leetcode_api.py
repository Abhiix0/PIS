import pytest
from unittest.mock import patch, MagicMock
from ingest.leetcode_api import fetch_leetcode_data, _parse_submission_stats


def _base_mock(recent_submissions: list, counts=None) -> MagicMock:
    """Build a standard mock response with configurable submissions and counts."""
    if counts is None:
        counts = [
            {"difficulty": "All",    "count": 10},
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
            },
            "recentSubmissionList": recent_submissions,
        }
    }
    return mock


def test_parse_submission_stats_correct():
    stats = [
        {"difficulty": "All",    "count": 150},
        {"difficulty": "Easy",   "count": 60},
        {"difficulty": "Medium", "count": 70},
        {"difficulty": "Hard",   "count": 20},
    ]
    result = _parse_submission_stats(stats)
    assert result["easy"]   == 60
    assert result["medium"] == 70
    assert result["hard"]   == 20


def test_fetch_leetcode_data_user_not_found():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {"matchedUser": None, "recentSubmissionList": []}
    }
    with patch("requests.post", return_value=mock_response):
        with pytest.raises(ValueError, match="not found or profile is private"):
            fetch_leetcode_data("definitely_not_a_real_user_xyz123")


def test_fetch_leetcode_data_returns_records():
    mock = _base_mock([{
        "titleSlug": "two-sum",
        "timestamp": "1700000000",
        "statusDisplay": "Accepted",
        "lang": "python3",
        "difficulty": {"level": 1},
    }])
    with patch("requests.post", return_value=mock):
        records = fetch_leetcode_data("testuser")
    assert len(records) > 0
    assert all(r["difficulty"] in ["easy", "medium", "hard"] for r in records)
    assert all("problem_id" in r for r in records)
    assert all("solved_at" in r for r in records)


def test_real_difficulty_level_used_when_present():
    """difficulty.level from the API must be used directly, not random.choices()."""
    mock = _base_mock([
        {"titleSlug": "two-sum",              "timestamp": "1700000000",
         "statusDisplay": "Accepted", "lang": "python3", "difficulty": {"level": 1}},
        {"titleSlug": "merge-k-sorted-lists", "timestamp": "1700001000",
         "statusDisplay": "Accepted", "lang": "python3", "difficulty": {"level": 3}},
        {"titleSlug": "add-two-numbers",      "timestamp": "1700002000",
         "statusDisplay": "Accepted", "lang": "python3", "difficulty": {"level": 2}},
    ])
    with patch("requests.post", return_value=mock):
        records = fetch_leetcode_data("testuser")

    # Find the real records (not synthesized) by their slug-based problem_id
    real = {r["problem_id"]: r for r in records if not r["problem_id"].endswith(("_0000", "_0001", "_0002", "_0003"))}
    slug_records = [r for r in records if "two_sum" in r["problem_id"] or
                    "merge_k_sorted" in r["problem_id"] or "add_two_numbers" in r["problem_id"]]

    assert any(r["difficulty"] == "easy"   for r in slug_records), "two-sum (level=1) should be easy"
    assert any(r["difficulty"] == "hard"   for r in slug_records), "merge-k (level=3) should be hard"
    assert any(r["difficulty"] == "medium" for r in slug_records), "add-two (level=2) should be medium"


def test_fetch_leetcode_api_timeout():
    import requests as req_lib
    with patch("requests.post", side_effect=req_lib.exceptions.Timeout):
        with pytest.raises(RuntimeError, match="timed out"):
            fetch_leetcode_data("anyuser")


def test_no_over_generation_when_real_submissions_exist():
    """Regression test for the _synthesize_records over-generation bug.

    User has solved 5 easy + 4 medium + 1 hard = 10 total.
    API returns 1 real accepted submission (two-sum, level=1 → easy).
    Total records must be exactly 10, not 20.
    """
    mock = _base_mock([{
        "titleSlug": "two-sum",
        "timestamp": "1700000000",
        "statusDisplay": "Accepted",
        "lang": "python3",
        "difficulty": {"level": 1},
    }])
    with patch("requests.post", return_value=mock):
        records = fetch_leetcode_data("testuser")

    assert len(records) == 10, (
        f"Expected exactly 10 records (matching total solved), got {len(records)}. "
        "Over-generation bug may have returned."
    )
