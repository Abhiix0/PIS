import pytest
from unittest.mock import patch, MagicMock
from ingest.leetcode_api import fetch_leetcode_data, _parse_submission_stats


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
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "matchedUser": {
                "username": "testuser",
                "submitStats": {
                    "acSubmissionNum": [
                        {"difficulty": "All",    "count": 10},
                        {"difficulty": "Easy",   "count": 5},
                        {"difficulty": "Medium", "count": 4},
                        {"difficulty": "Hard",   "count": 1},
                    ]
                }
            },
            "recentSubmissionList": [
                {
                    "titleSlug": "two-sum",
                    "timestamp": "1700000000",
                    "statusDisplay": "Accepted",
                    "lang": "python3",
                },
            ]
        }
    }
    with patch("requests.post", return_value=mock_response):
        records = fetch_leetcode_data("testuser")
    assert len(records) > 0
    assert all(r["difficulty"] in ["easy", "medium", "hard"] for r in records)
    assert all("problem_id" in r for r in records)
    assert all("solved_at" in r for r in records)


def test_fetch_leetcode_api_timeout():
    import requests as req_lib
    with patch("requests.post", side_effect=req_lib.exceptions.Timeout):
        with pytest.raises(RuntimeError, match="timed out"):
            fetch_leetcode_data("anyuser")
