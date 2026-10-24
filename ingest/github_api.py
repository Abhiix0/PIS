"""GitHub adapter: public REST data -> typed observations.

Only public data of a public username is read. Any failure raises ProviderError; nothing here ever
turns a failed request into a count. See docs/data/provenance.md for what each observation means.
"""

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta

import requests

from ingest.provider import Observation, ProviderError

GITHUB_API_BASE = "https://api.github.com"
PAYLOAD_VERSION = "github-rest-v1"
USERNAME_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$"
)  # also keeps the name safe to put in a URL path
MAX_REPOS = 10  # each repo costs one API call; unauthenticated budget is 60 requests/hour
_PAGE_SIZE = 100
_MAX_PAGES = 3
_ATTEMPTS = 3  # bounded retries, only for timeouts and 5xx
_BACKOFF = 1.0  # seconds, doubled per attempt
GRAPHQL_URL = f"{GITHUB_API_BASE}/graphql"
CALENDAR_DAYS = (
    365  # docs/research/github-calendar-spike.md: spans up to 1 year accepted, 400 days rejected
)
CALENDAR_PAYLOAD_VERSION = "github-graphql-calendar-v1"
_CALENDAR_QUERY = (
    "query($u:String!,$f:DateTime!,$t:DateTime!){user(login:$u){contributionsCollection(from:$f,to:$t)"
    "{contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"
)


def _headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv(
        "GITHUB_TOKEN", ""
    )  # optional server-side token; never sent to or stored for clients
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(url: str, params: dict | None, body: dict | None = None) -> requests.Response:
    """GET with bounded retries; a `body` makes it a POST (GraphQL)."""
    last = ProviderError("unavailable")
    for attempt in range(_ATTEMPTS):
        try:
            if body is None:
                resp = requests.get(url, headers=_headers(), params=params, timeout=10)
            else:
                resp = requests.post(url, headers=_headers(), json=body, timeout=10)
            if resp.status_code < 500:
                return resp
        except (requests.Timeout, requests.ConnectionError):
            pass
        if attempt < _ATTEMPTS - 1:
            time.sleep(_BACKOFF * 2**attempt)
    raise last


def _check(resp: requests.Response, allow=(200,)) -> None:
    """Map an HTTP status to a ProviderError. Rate limits are reported, never retried."""
    s = resp.status_code
    if s in allow:
        return
    header = resp.headers.get("Retry-After")
    retry = int(header) if isinstance(header, str) and header.isdigit() else None
    if s == 404:
        raise ProviderError("not_found")
    if s == 429 or (
        s == 403 and (resp.headers.get("X-RateLimit-Remaining") == "0" or retry is not None)
    ):
        raise ProviderError("rate_limited", retry_after=retry)
    if s in (401, 403):
        raise ProviderError("forbidden")
    raise ProviderError("unavailable", f"HTTP {s}")


def _json(resp: requests.Response):
    try:
        return resp.json()
    except ValueError:
        raise ProviderError("malformed", "response is not JSON") from None


def _list_repos(username: str) -> tuple[list[dict], bool]:
    """Public, non-fork repos, most recently pushed first. Returns (repos, truncated)."""
    repos, truncated = [], False
    for page in range(1, _MAX_PAGES + 1):
        resp = _get(
            f"{GITHUB_API_BASE}/users/{username}/repos",
            {"per_page": _PAGE_SIZE, "page": page, "type": "owner", "sort": "pushed"},
        )
        _check(resp)
        batch = _json(resp)
        if not isinstance(batch, list) or not all(isinstance(r, dict) for r in batch):
            raise ProviderError("malformed", "repo list has unexpected shape")
        repos += [r for r in batch if not r.get("fork")]
        if len(batch) < _PAGE_SIZE:
            break
        if page == _MAX_PAGES:
            truncated = True
    if len(repos) > MAX_REPOS:
        repos, truncated = repos[:MAX_REPOS], True
    return repos, truncated


def _commit_count(username: str, repo: str) -> int:
    """Commits authored by `username` in the repo, via the page count of a 1-per-page listing."""
    resp = _get(
        f"{GITHUB_API_BASE}/repos/{username}/{repo}/commits", {"per_page": 1, "author": username}
    )
    if resp.status_code == 409:  # empty repository
        return 0
    _check(resp)
    m = re.search(r'[?&]page=(\d+)[^>]*>;\s*rel="last"', resp.headers.get("Link", ""))
    if m:
        return int(m.group(1))
    body = _json(resp)
    if not isinstance(body, list):
        raise ProviderError("malformed", "commit list has unexpected shape")
    return len(body)


def _pushed_at(repo: dict) -> datetime | None:
    raw = repo.get("pushed_at")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise ProviderError("malformed", "pushed_at is not an ISO timestamp") from None


def fetch_github_observations(username: str) -> tuple[list[Observation], bool]:
    """Return (observations, partial). partial=True means some repos were skipped or truncated.

    Raises ProviderError if the user cannot be read at all, or every per-repo lookup failed.
    """
    if not USERNAME_RE.match(username or ""):
        raise ProviderError("not_found", "invalid GitHub username")
    repos, partial = _list_repos(username)
    names = []
    for r in repos:
        if not isinstance(r.get("name"), str) or not r["name"]:
            raise ProviderError("malformed", "repo without a name")
        names.append(r["name"])

    def count(name):
        try:
            return _commit_count(username, name), None
        except ProviderError as e:
            return None, e

    with ThreadPoolExecutor(max_workers=5) as ex:
        counts = list(ex.map(count, names))
    if names and all(c is None for c, _ in counts):
        raise counts[0][
            1
        ]  # nothing usable came back: fail the run rather than report an empty profile

    obs = [
        Observation(
            "github", "github_public_repo_count", len(repos), payload_version=PAYLOAD_VERSION
        )
    ]
    for repo, (n, err) in zip(repos, counts):
        if err is not None:
            partial = True
            continue
        pushed = _pushed_at(repo)
        obs.append(
            Observation(
                "github",
                "github_repo_commit_count",
                n,
                source_object_id=repo["name"],
                event_at=pushed,
                event_at_precision="repo_push" if pushed else "unknown",
                payload_version=PAYLOAD_VERSION,
            )
        )
    return obs, partial


def fetch_github_calendar_observations(
    username: str, today: date | None = None
) -> tuple[list[Observation], bool]:
    """Daily contribution counts for the last CALENDAR_DAYS UTC days ending `today`. Returns (observations, partial).

    A day the provider reports with 0 is a measured zero; a day it does not report is absent, never zero.
    partial=True means the calendar had fewer days than the window. Anything else wrong raises ProviderError.
    """
    if not USERNAME_RE.match(username or ""):
        raise ProviderError("not_found", "invalid GitHub username")
    if "Authorization" not in _headers():
        raise ProviderError("disabled", "GitHub GraphQL needs a server GITHUB_TOKEN")
    today = today or datetime.now(UTC).date()
    first = today - timedelta(days=CALENDAR_DAYS - 1)
    # exact UTC dates need UTC-midnight bounds (spike: "Practical rule")
    frm = f"{first.isoformat()}T00:00:00Z"
    to = f"{today.isoformat()}T23:59:59Z"
    resp = _get(
        GRAPHQL_URL,
        None,
        {"query": _CALENDAR_QUERY, "variables": {"u": username, "f": frm, "t": to}},
    )
    _check(resp)
    body = _json(resp)
    if not isinstance(body, dict):
        raise ProviderError("malformed", "GraphQL response has unexpected shape")
    errors = body.get("errors")
    if (
        errors
    ):  # GraphQL reports failures with HTTP 200; the error types are from GitHub docs, not observed
        types = {e.get("type") for e in errors if isinstance(e, dict)}
        if "NOT_FOUND" in types:
            raise ProviderError("not_found")
        if "RATE_LIMITED" in types:
            raise ProviderError("rate_limited")
        raise ProviderError("unavailable", "GraphQL error")
    try:
        raw = [
            d
            for w in body["data"]["user"]["contributionsCollection"]["contributionCalendar"][
                "weeks"
            ]
            for d in w["contributionDays"]
        ]
    except (KeyError, TypeError):
        raise ProviderError("malformed", "calendar missing from response") from None

    counts: dict[date, int] = {}
    for d in raw:
        try:
            day, n = date.fromisoformat(d["date"]), d["contributionCount"]
        except (KeyError, TypeError, ValueError):
            raise ProviderError("malformed", "calendar day has unexpected shape") from None
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ProviderError("malformed", "contributionCount is not a non-negative integer")
        if day in counts:
            raise ProviderError("malformed", "calendar day listed twice")
        if first <= day <= today:
            counts[day] = n
    if not counts:
        raise ProviderError("malformed", "calendar has no days in the window")
    obs = [
        Observation(
            "github",
            "github_contribution_day",
            n,
            granularity="event",
            source_object_id=day.isoformat(),
            event_at=datetime(day.year, day.month, day.day, tzinfo=UTC),
            event_at_precision="day",
            payload_version=CALENDAR_PAYLOAD_VERSION,
        )
        for day, n in sorted(counts.items())
    ]
    return obs, len(counts) < CALENDAR_DAYS
