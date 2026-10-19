from unittest.mock import MagicMock, patch

import pytest
import requests

from ingest.github_api import fetch_github_observations
from ingest.provider import ProviderError


def resp(status=200, body=None, headers=None):
    r = MagicMock()
    r.status_code = status
    r.headers = headers or {}
    if body is ValueError:
        r.json.side_effect = ValueError("not json")
    else:
        r.json.return_value = body
    return r


def repo(name, fork=False, pushed="2024-03-01T12:00:00Z"):
    return {"name": name, "fork": fork, "pushed_at": pushed}


def last_page(n):
    return {"Link": f'<https://api.github.com/x?per_page=1&author=u&page={n}>; rel="last"'}


def router(listing, commits):
    """requests.get stand-in: `listing` answers /users/..., `commits(repo_name)` answers /repos/.../commits."""

    def fake(url, **kw):
        if "/users/" in url:
            return listing
        return commits(url.split("/")[-2])

    return fake


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("ingest.github_api.time.sleep"):
        yield


def by_type(obs):
    return {(o.observation_type, o.source_object_id): o for o in obs}


def test_success_records_author_commit_counts_with_repo_push_precision():
    fake = router(resp(body=[repo("a")]), lambda r: resp(body=[{}], headers=last_page(42)))
    with patch("requests.get", side_effect=fake) as g:
        obs, partial = fetch_github_observations("testuser")
    assert partial is False
    o = by_type(obs)
    assert o[("github_public_repo_count", None)].value_num == 1
    c = o[("github_repo_commit_count", "a")]
    assert (c.value_num, c.event_at_precision, c.granularity, c.provenance) == (
        42,
        "repo_push",
        "aggregate",
        "observed",
    )
    commit_call = [c for c in g.call_args_list if "/commits" in c.args[0]][0]
    assert (
        commit_call.kwargs["params"]["author"] == "testuser"
    )  # attributed commits, not the repo total


def test_forks_are_excluded():
    fake = router(resp(body=[repo("f", fork=True), repo("a")]), lambda r: resp(body=[{}]))
    with patch("requests.get", side_effect=fake):
        obs, _ = fetch_github_observations("testuser")
    assert [o.source_object_id for o in obs if o.source_object_id] == ["a"]


def test_empty_profile_is_an_explicit_measured_zero_not_a_missing_result():
    with patch("requests.get", return_value=resp(body=[])):
        obs, partial = fetch_github_observations("testuser")
    assert partial is False and len(obs) == 1
    assert obs[0].value_num == 0 and obs[0].value_state == "measured_zero"


def test_empty_repo_counts_zero_commits():
    fake = router(resp(body=[repo("a")]), lambda r: resp(status=409))
    with patch("requests.get", side_effect=fake):
        obs, _ = fetch_github_observations("testuser")
    assert by_type(obs)[("github_repo_commit_count", "a")].value_num == 0


@pytest.mark.parametrize(
    "status,headers,code",
    [
        (404, {}, "not_found"),
        (429, {"Retry-After": "30"}, "rate_limited"),
        (403, {"X-RateLimit-Remaining": "0"}, "rate_limited"),
        (403, {"Retry-After": "60"}, "rate_limited"),
        (403, {}, "forbidden"),
        (401, {}, "forbidden"),
        (422, {}, "unavailable"),
    ],
)
def test_listing_errors_map_to_safe_codes(status, headers, code):
    with patch("requests.get", return_value=resp(status, headers=headers)):
        with pytest.raises(ProviderError) as e:
            fetch_github_observations("testuser")
    assert e.value.code == code


def test_rate_limit_reports_retry_after_and_is_not_retried():
    with patch("requests.get", return_value=resp(429, headers={"Retry-After": "30"})) as g:
        with pytest.raises(ProviderError) as e:
            fetch_github_observations("testuser")
    assert e.value.retry_after == 30 and g.call_count == 1


def test_unavailable_is_retried_a_bounded_number_of_times():
    with patch("requests.get", return_value=resp(503)) as g:
        with pytest.raises(ProviderError) as e:
            fetch_github_observations("testuser")
    assert e.value.code == "unavailable" and g.call_count == 3


def test_timeout_then_success_recovers():
    with patch("requests.get", side_effect=[requests.Timeout(), resp(body=[])]):
        obs, _ = fetch_github_observations("testuser")
    assert obs[0].value_num == 0


@pytest.mark.parametrize("body", [{"message": "x"}, ["not-a-dict"], ValueError])
def test_malformed_listing_raises(body):
    with patch("requests.get", return_value=resp(body=body)):
        with pytest.raises(ProviderError) as e:
            fetch_github_observations("testuser")
    assert e.value.code == "malformed"


def test_partial_when_one_repo_lookup_fails_and_that_repo_is_omitted_not_guessed():
    fake = router(
        resp(body=[repo("a"), repo("b")]),
        lambda r: resp(500) if r == "b" else resp(body=[{}], headers=last_page(5)),
    )
    with patch("requests.get", side_effect=fake):
        obs, partial = fetch_github_observations("testuser")
    assert partial is True
    assert ("github_repo_commit_count", "b") not in by_type(obs)
    assert by_type(obs)[("github_repo_commit_count", "a")].value_num == 5


def test_every_repo_failing_fails_the_whole_fetch():
    fake = router(resp(body=[repo("a")]), lambda r: resp(429, headers={"Retry-After": "5"}))
    with patch("requests.get", side_effect=fake):
        with pytest.raises(ProviderError) as e:
            fetch_github_observations("testuser")
    assert e.value.code == "rate_limited"


def test_more_repos_than_the_cap_is_partial():
    fake = router(resp(body=[repo(f"r{i}") for i in range(11)]), lambda r: resp(body=[{}]))
    with patch("requests.get", side_effect=fake):
        obs, partial = fetch_github_observations("testuser")
    assert partial is True and len(obs) == 11  # repo-count observation + 10 repos


@pytest.mark.parametrize("name", ["", "../etc", "a/b", "a b", "-x", "x" * 40])
def test_bad_username_never_reaches_the_network(name):
    with patch("requests.get") as g:
        with pytest.raises(ProviderError) as e:
            fetch_github_observations(name)
    assert e.value.code == "not_found" and g.call_count == 0


# --- daily contribution calendar (GraphQL) ---
from datetime import date, timedelta  # noqa: E402

from ingest.github_api import CALENDAR_DAYS, fetch_github_calendar_observations  # noqa: E402

TODAY = date(2026, 10, 19)


def cal_body(counts):
    return {
        "data": {
            "user": {
                "contributionsCollection": {
                    "contributionCalendar": {
                        "weeks": [
                            {"contributionDays": [{"date": d.isoformat(), "contributionCount": n}]}
                            for d, n in counts
                        ]
                    }
                }
            }
        }
    }


def full_window(n=lambda i: 0):
    return [(TODAY - timedelta(days=CALENDAR_DAYS - 1 - i), n(i)) for i in range(CALENDAR_DAYS)]


@pytest.fixture
def token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "t")


def fetch_cal(body=None, **kw):
    with patch("requests.post", return_value=resp(body=body, **kw)) as p:
        return fetch_github_calendar_observations("testuser", today=TODAY), p


def test_calendar_success_is_event_day_observations_for_a_full_window(token):
    (obs, partial), p = fetch_cal(cal_body(full_window(lambda i: i % 3)))
    assert partial is False and len(obs) == CALENDAR_DAYS
    last = obs[-1]
    assert (last.observation_type, last.source_object_id, last.granularity, last.provenance) == (
        "github_contribution_day",
        "2026-10-19",
        "event",
        "observed",
    )
    assert (last.event_at.isoformat(), last.event_at_precision) == (
        "2026-10-19T00:00:00+00:00",
        "day",
    )
    v = p.call_args.kwargs["json"]["variables"]
    assert (v["u"], v["f"], v["t"]) == ("testuser", "2025-10-20T00:00:00Z", "2026-10-19T23:59:59Z")


def test_calendar_zero_days_are_measured_zero_not_missing(token):
    (obs, partial), _ = fetch_cal(cal_body(full_window()))
    assert partial is False and len(obs) == CALENDAR_DAYS
    assert {o.value_state for o in obs} == {"measured_zero"}


def test_calendar_truncated_window_is_partial_and_gaps_are_not_filled(token):
    (obs, partial), _ = fetch_cal(cal_body(full_window()[100:]))
    assert partial is True and len(obs) == CALENDAR_DAYS - 100


def test_calendar_days_outside_the_window_are_dropped(token):
    extra = [(TODAY - timedelta(days=CALENDAR_DAYS), 9), (TODAY + timedelta(days=1), 9)]
    (obs, _), _ = fetch_cal(cal_body(extra + full_window()))
    assert len(obs) == CALENDAR_DAYS and all(o.value_num == 0 for o in obs)


def test_calendar_partial_when_only_some_days_come_back(token):
    (obs, partial), _ = fetch_cal(cal_body([(TODAY, 4)]))
    assert partial is True and [o.value_num for o in obs] == [4]


@pytest.mark.parametrize(
    "status,headers,code",
    [
        (429, {"Retry-After": "30"}, "rate_limited"),
        (403, {"X-RateLimit-Remaining": "0"}, "rate_limited"),
        (404, {}, "not_found"),
    ],
)
def test_calendar_http_errors_raise(token, status, headers, code):
    with pytest.raises(ProviderError) as e:
        fetch_cal(status=status, headers=headers)
    assert e.value.code == code


@pytest.mark.parametrize(
    "errors,code",
    [
        ([{"type": "RATE_LIMITED"}], "rate_limited"),
        ([{"type": "NOT_FOUND"}], "not_found"),
        ([{"message": "total time spanned"}], "unavailable"),
    ],
)
def test_calendar_graphql_errors_raise_even_with_http_200(token, errors, code):
    with pytest.raises(ProviderError) as e:
        fetch_cal({"errors": errors, "data": None})
    assert e.value.code == code


def _raw_day(day):
    weeks = [{"contributionDays": [day]}]
    return {
        "data": {"user": {"contributionsCollection": {"contributionCalendar": {"weeks": weeks}}}}
    }


@pytest.mark.parametrize(
    "body",
    [
        ValueError,
        ["x"],
        {"data": {"user": None}},
        cal_body([]),
        _raw_day({"date": "nope", "contributionCount": 1}),
        cal_body([(TODAY, -1)]),
        cal_body([(TODAY, True)]),
        cal_body([(TODAY, "3")]),
        cal_body([(TODAY, 1), (TODAY, 1)]),
    ],
)
def test_calendar_malformed_raises_never_returns_empty(token, body):
    with pytest.raises(ProviderError) as e:
        fetch_cal(body)
    assert e.value.code == "malformed"


def test_calendar_without_server_token_is_disabled_and_never_calls_out(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with patch("requests.post") as p:
        with pytest.raises(ProviderError) as e:
            fetch_github_calendar_observations("testuser", today=TODAY)
    assert e.value.code == "disabled" and p.call_count == 0
