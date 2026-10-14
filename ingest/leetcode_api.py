"""LeetCode adapter: solved counts by difficulty, stored as aggregates.

The endpoint is unofficial and its terms are unverified (docs/research/data-source-feasibility.md), so the
sync service only calls this when LEETCODE_INTEGRATION_ENABLED is set. Per-problem rows and solve dates are
NOT observable from this query and are never generated.
"""
import re

import requests

from ingest.provider import Observation, ProviderError

LEETCODE_GQL_URL = "https://leetcode.com/graphql"
PAYLOAD_VERSION = "leetcode-gql-submitstats-v1"
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,40}$")

# Username goes in as a GraphQL variable, never interpolated into the query text.
PROFILE_QUERY = """
query($u: String!) {
  matchedUser(username: $u) {
    username
    submitStats { acSubmissionNum { difficulty count } }
  }
}
"""
_DIFFICULTIES = {"Easy": "easy", "Medium": "medium", "Hard": "hard"}


def _parse_submission_stats(stats: list) -> dict:
    """Parse acSubmissionNum into {easy, medium, hard}. A missing or non-integer count is malformed, not zero."""
    counts = {}
    for entry in stats:
        name = _DIFFICULTIES.get(entry.get("difficulty", "")) if isinstance(entry, dict) else None
        if name is None:
            continue  # the 'All' summary row and anything unknown
        c = entry.get("count")
        if not isinstance(c, int) or isinstance(c, bool) or c < 0:
            raise ProviderError("malformed", f"bad count for {name}")
        counts[name] = c
    if set(counts) != set(_DIFFICULTIES.values()):
        raise ProviderError("malformed", "missing difficulty rows")
    return counts


def fetch_leetcode_observations(username: str) -> tuple[list[Observation], bool]:
    """Return (observations, partial=False). Raises ProviderError on any failure."""
    if not USERNAME_RE.match(username or ""):
        raise ProviderError("not_found", "invalid LeetCode username")
    try:
        resp = requests.post(LEETCODE_GQL_URL, json={"query": PROFILE_QUERY, "variables": {"u": username}},
                             headers={"Content-Type": "application/json", "Referer": "https://leetcode.com"},
                             timeout=15)
    except (requests.Timeout, requests.ConnectionError):
        raise ProviderError("unavailable", "LeetCode unreachable")
    if resp.status_code == 429:
        raise ProviderError("rate_limited")
    if resp.status_code != 200:
        raise ProviderError("unavailable", f"HTTP {resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        raise ProviderError("malformed", "response is not JSON")
    if not isinstance(data, dict) or data.get("errors"):
        raise ProviderError("malformed", "GraphQL error or unexpected shape")
    user = (data.get("data") or {}).get("matchedUser")
    if not user:
        raise ProviderError("not_found", "user not found or profile private")
    stats = (user.get("submitStats") or {}).get("acSubmissionNum")
    if not isinstance(stats, list) or not stats:
        raise ProviderError("malformed", "no submission stats")
    counts = _parse_submission_stats(stats)
    return [Observation("leetcode", f"leetcode_solved_{d}", n, payload_version=PAYLOAD_VERSION)
            for d, n in counts.items()], False
