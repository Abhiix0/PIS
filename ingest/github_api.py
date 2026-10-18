"""GitHub adapter: public REST data -> typed observations.

Only public data of a public username is read. Any failure raises ProviderError; nothing here ever
turns a failed request into a count. See docs/data/provenance.md for what each observation means.
"""

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

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


def _headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv(
        "GITHUB_TOKEN", ""
    )  # optional server-side token; never sent to or stored for clients
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(url: str, params: dict) -> requests.Response:
    last = ProviderError("unavailable")
    for attempt in range(_ATTEMPTS):
        try:
            resp = requests.get(url, headers=_headers(), params=params, timeout=10)
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
    retry = resp.headers.get("Retry-After")
    retry = int(retry) if isinstance(retry, str) and retry.isdigit() else None
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
