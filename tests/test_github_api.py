import pytest
from unittest.mock import patch, MagicMock
from ingest.github_api import fetch_github_data


def _mock_repos_response():
    mock = MagicMock()
    mock.status_code = 200
    mock.headers = {}  # no Link header = single page
    mock.json.return_value = [
        {
            "name":       "my-project",
            "pushed_at":  "2024-03-01T12:00:00Z",
            "updated_at": "2024-03-01T12:00:00Z",
            "size":       100,
        }
    ]
    return mock


def _mock_commits_response(count=42):
    mock = MagicMock()
    mock.status_code = 200
    mock.headers = {
        "Link": f'<https://api.github.com/repos/x/y/commits?page={count}>; rel="last"'
    }
    mock.json.return_value = [{"sha": "abc"}]
    return mock


def test_fetch_github_data_returns_records():
    with patch("requests.get") as mock_get:
        mock_get.side_effect = [
            _mock_repos_response(),      # repos list call
            _mock_commits_response(42),  # commits call for repo
        ]
        records = fetch_github_data("testuser")

    assert len(records) == 1
    assert records[0]["repo_name"] == "my-project"
    assert records[0]["commits"] == 42
    assert "commit_date" in records[0]


def test_fetch_github_data_user_not_found():
    mock = MagicMock()
    mock.status_code = 404
    mock.raise_for_status.side_effect = Exception("404")
    with patch("requests.get", return_value=mock):
        with pytest.raises(ValueError, match="not found"):
            fetch_github_data("nonexistent_user_xyz")


def test_fetch_github_data_rate_limited():
    mock = MagicMock()
    mock.status_code = 403
    with patch("requests.get", return_value=mock):
        with pytest.raises(RuntimeError, match="rate limit"):
            fetch_github_data("someuser")
