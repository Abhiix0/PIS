from unittest.mock import MagicMock, patch

import pytest
import requests

from ingest.leetcode_api import _parse_submission_stats, fetch_leetcode_observations
from ingest.provider import ProviderError


def gql(counts=None, status=200, body=None):
    if counts is None:
        counts = [{"difficulty": "All", "count": 10}, {"difficulty": "Easy", "count": 5},
                  {"difficulty": "Medium", "count": 4}, {"difficulty": "Hard", "count": 1}]
    m = MagicMock()
    m.status_code = status
    m.json.return_value = body if body is not None else {
        "data": {"matchedUser": {"username": "u", "submitStats": {"acSubmissionNum": counts}}}}
    return m


def test_returns_three_aggregates_and_no_per_problem_rows_or_dates():
    with patch("requests.post", return_value=gql()):
        obs, partial = fetch_leetcode_observations("testuser")
    assert partial is False
    assert {o.observation_type: o.value_num for o in obs} == {
        "leetcode_solved_easy": 5, "leetcode_solved_medium": 4, "leetcode_solved_hard": 1}
    assert all(o.granularity == "aggregate" and o.event_at is None and o.event_at_precision == "unknown" for o in obs)


def test_username_is_a_graphql_variable_not_interpolated():
    with patch("requests.post", return_value=gql()) as p:
        fetch_leetcode_observations("testuser")
    sent = p.call_args.kwargs["json"]
    assert sent["variables"] == {"u": "testuser"} and "testuser" not in sent["query"]


def test_zero_solved_is_measured_zero():
    zeros = [{"difficulty": d, "count": 0} for d in ("Easy", "Medium", "Hard")]
    with patch("requests.post", return_value=gql(zeros)):
        obs, _ = fetch_leetcode_observations("testuser")
    assert all(o.value_num == 0 and o.value_state == "measured_zero" for o in obs)


def test_parse_stats_missing_or_bad_count_is_malformed_not_zero():
    with pytest.raises(ProviderError) as e:
        _parse_submission_stats([{"difficulty": "Easy", "count": 3}, {"difficulty": "Medium", "count": 1}])
    assert e.value.code == "malformed"
    with pytest.raises(ProviderError):
        _parse_submission_stats([{"difficulty": d, "count": "7"} for d in ("Easy", "Medium", "Hard")])


@pytest.mark.parametrize("kw,code", [
    (dict(body={"data": {"matchedUser": None}}), "not_found"),
    (dict(status=429), "rate_limited"),
    (dict(status=503), "unavailable"),
    (dict(body={"errors": [{"message": "x"}]}), "malformed"),
    (dict(body={"data": {"matchedUser": {"submitStats": {"acSubmissionNum": []}}}}), "malformed"),
    (dict(body={"data": {"matchedUser": {"submitStats": None}}}), "malformed"),
    (dict(body=["unexpected"]), "malformed"),
])
def test_failures_map_to_safe_codes(kw, code):
    with patch("requests.post", return_value=gql(**kw)):
        with pytest.raises(ProviderError) as e:
            fetch_leetcode_observations("testuser")
    assert e.value.code == code


@pytest.mark.parametrize("exc", [requests.Timeout, requests.ConnectionError])
def test_network_failure_is_unavailable(exc):
    with patch("requests.post", side_effect=exc):
        with pytest.raises(ProviderError) as e:
            fetch_leetcode_observations("testuser")
    assert e.value.code == "unavailable"


def test_non_json_is_malformed():
    m = gql()
    m.json.side_effect = ValueError()
    with patch("requests.post", return_value=m):
        with pytest.raises(ProviderError) as e:
            fetch_leetcode_observations("testuser")
    assert e.value.code == "malformed"


def test_bad_username_never_reaches_the_network():
    with patch("requests.post") as p:
        with pytest.raises(ProviderError):
            fetch_leetcode_observations('x"){evil}')
    assert p.call_count == 0
