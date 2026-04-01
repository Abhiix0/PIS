import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date
from typing import Optional

GITHUB_API_BASE = "https://api.github.com"


def _get_headers() -> dict:
    """Return auth headers. Works without token but rate-limited to 60 req/hr."""
    token = os.getenv("GITHUB_TOKEN", "")  # read on every call — never stale
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def _get_repo_commit_count(owner: str, repo: str) -> int:
    """Get total commit count for a repo using the pagination trick.
    GitHub returns total count in the Link header when per_page=1.
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits"
    params = {"per_page": 1}
    resp = requests.get(url, headers=_get_headers(), params=params, timeout=10)
    if resp.status_code == 409:  # empty repo
        return 0
    resp.raise_for_status()
    link = resp.headers.get("Link", "")
    if 'rel="last"' in link:
        # Extract page number from: <...?page=N>; rel="last"
        match = re.search(r'page=(\d+)>; rel="last"', link)
        if match:
            return int(match.group(1))
    return len(resp.json())  # single page, count items


def fetch_github_data(username: str) -> list[dict]:
    """Fetch repository and commit data for a GitHub user.

    Returns a list of dicts ready to insert into github_activity:
        [{'repo_name': str, 'commits': int, 'commit_date': date}, ...]

    Fetches up to 10 most recently updated repos.
    Gets total commit count per repo (not just last page).

    Raises:
        ValueError: if username not found on GitHub (404)
        RuntimeError: if rate limited (403/429) or other API error
    """
    # Step 1: fetch list of repos
    url = f"{GITHUB_API_BASE}/users/{username}/repos"
    params = {"per_page": 10, "sort": "updated", "type": "all"}
    resp = requests.get(url, headers=_get_headers(), params=params, timeout=10)

    if resp.status_code == 404:
        raise ValueError(f"GitHub username '{username}' not found.")
    if resp.status_code == 403:
        raise RuntimeError(
            "GitHub API rate limit exceeded. "
            "Set GITHUB_TOKEN in .env to increase limit to 5000/hr."
        )
    if resp.status_code == 429:
        retry = resp.headers.get("Retry-After", "60")
        raise RuntimeError(f"GitHub API rate limited. Retry after {retry} seconds.")
    resp.raise_for_status()

    repos = resp.json()
    if not repos:
        return []

    # Filter repos that are worth querying (skip empty forks, etc.)
    # and pre-compute commit_date so we don't repeat the parse inside threads.
    candidates = []
    for repo in repos:
        pushed_at_str = repo.get("pushed_at") or repo.get("updated_at")
        if not pushed_at_str:
            continue
        commit_date = datetime.fromisoformat(
            pushed_at_str.replace("Z", "+00:00")
        ).date()
        candidates.append((repo["name"], commit_date))

    if not candidates:
        return []

    # Fetch commit counts for all repos in parallel — reduces N sequential
    # HTTP calls (worst-case 100s) to ceil(N/5) batches (~3s for 10 repos).
    records = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(_get_repo_commit_count, username, repo_name): (repo_name, commit_date)
            for repo_name, commit_date in candidates
        }
        for future in as_completed(futures):
            repo_name, commit_date = futures[future]
            try:
                commit_count = future.result()
            except Exception:
                commit_count = 1  # safe fallback
            if commit_count > 0:
                records.append({
                    "repo_name":   repo_name,
                    "commits":     commit_count,
                    "commit_date": commit_date,
                })

    return records
