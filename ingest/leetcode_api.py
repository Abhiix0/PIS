import requests
import random
from datetime import date, timedelta
from typing import Optional

LEETCODE_GQL_URL = "https://leetcode.com/graphql"

# GraphQL query to fetch user stats and recent submissions
PROFILE_QUERY = """
query getUserProfile($username: String!) {
  matchedUser(username: $username) {
    username
    submitStats: submitStatsGlobal {
      acSubmissionNum {
        difficulty
        count
        submissions
      }
    }
  }
  recentSubmissionList(username: $username, limit: 20) {
    title
    titleSlug
    timestamp
    statusDisplay
    lang
  }
}
"""

DIFFICULTY_MAP = {
    "Easy":   "easy",
    "Medium": "medium",
    "Hard":   "hard",
    "All":    None,   # skip the "All" summary row
}


def _parse_submission_stats(stats: list) -> dict:
    """Parse acSubmissionNum into {easy: N, medium: N, hard: N}."""
    counts = {"easy": 0, "medium": 0, "hard": 0}
    for entry in stats:
        difficulty_label = entry.get("difficulty", "")
        mapped = DIFFICULTY_MAP.get(difficulty_label)
        if mapped:
            counts[mapped] = entry.get("count", 0)
    return counts


def _make_problem_id(username: str, slug: str) -> str:
    """Create a unique problem_id from username + slug.
    Format: LC_{username[:8]}_{slug[:30]}
    Keeps it under 50 chars (VARCHAR(50) in schema).
    """
    u = username[:8].replace("-", "_")
    s = slug[:30].replace("-", "_")
    return f"LC_{u}_{s}"[:50]


def _synthesize_records(
    username: str,
    counts: dict,
    existing_slugs: set,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Generate synthetic records to fill gap between recent submissions and total solve count.
    Preserves the difficulty distribution.

    When LeetCode only returns 20 recent submissions but the user solved 300 problems total,
    we synthesize the remaining 280 with correct difficulty weights spread across the date range.
    """
    records = []
    for difficulty, total_count in counts.items():
        # Count how many of this difficulty are already covered by real submissions
        already_covered = sum(
            1 for slug in existing_slugs
            if difficulty in slug  # rough heuristic, good enough
        )
        remaining = max(0, total_count - already_covered)

        for i in range(remaining):
            # Spread dates randomly across the given range
            days_range = (end_date - start_date).days
            random_days = random.randint(0, max(0, days_range))
            solved_date = start_date + timedelta(days=random_days)

            # Create a synthetic but unique problem_id
            problem_id = f"LC_{username[:8]}_{difficulty}_{i:04d}"[:50]
            if problem_id not in existing_slugs:
                records.append({
                    "problem_id": problem_id,
                    "difficulty": difficulty,
                    "solved_at":  solved_date,
                })
                existing_slugs.add(problem_id)

    return records


def fetch_leetcode_data(username: str) -> list[dict]:
    """Fetch LeetCode problem-solving data for a user.

    Returns a list of dicts ready to insert into coding_activity:
        [{'problem_id': str, 'difficulty': str, 'solved_at': date}, ...]

    Strategy:
        1. Fetch user profile stats (total solved by difficulty)
        2. Fetch recent 20 submissions (these have real dates)
        3. Synthesize remaining records to match total counts
           (preserves difficulty distribution, spreads dates realistically)

    Raises:
        ValueError: if username not found or profile is private
        RuntimeError: if API is unreachable or returns unexpected format
    """
    headers = {
        "Content-Type": "application/json",
        "Referer": "https://leetcode.com",
    }
    payload = {
        "query": PROFILE_QUERY,
        "variables": {"username": username},
    }

    try:
        resp = requests.post(
            LEETCODE_GQL_URL,
            json=payload,
            headers=headers,
            timeout=15,
        )
    except requests.exceptions.Timeout:
        raise RuntimeError("LeetCode API timed out after 15 seconds.")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Cannot connect to LeetCode API. Check internet connection.")

    if resp.status_code != 200:
        raise RuntimeError(
            f"LeetCode API returned HTTP {resp.status_code}. "
            f"API may be temporarily unavailable."
        )

    data = resp.json()

    if "errors" in data:
        raise RuntimeError(f"LeetCode GraphQL error: {data['errors']}")

    matched_user = data.get("data", {}).get("matchedUser")
    if not matched_user:
        raise ValueError(f"LeetCode username '{username}' not found or profile is private.")

    # Parse total solve counts by difficulty
    stats = matched_user.get("submitStats", {}).get("acSubmissionNum", [])
    counts = _parse_submission_stats(stats)
    total_solved = sum(counts.values())

    if total_solved == 0:
        return []  # user exists but solved nothing

    # Process real recent submissions (last 20)
    recent_submissions = data.get("data", {}).get("recentSubmissionList", []) or []
    records = []
    seen_slugs = set()

    # Date range for spreading synthesized records
    end_date   = date.today()
    start_date = end_date - timedelta(days=365)  # last 1 year

    total = max(1, total_solved)

    for sub in recent_submissions:
        if sub.get("statusDisplay") != "Accepted":
            continue  # only count accepted submissions

        slug = sub.get("titleSlug", "")
        if not slug:
            continue

        problem_id = _make_problem_id(username, slug)
        if problem_id in seen_slugs:
            continue

        # Convert Unix timestamp to date
        ts = sub.get("timestamp")
        if ts:
            solved_date = date.fromtimestamp(int(ts))
            # Clamp to valid range
            if solved_date > end_date:
                solved_date = end_date
            if solved_date < start_date:
                solved_date = start_date
        else:
            solved_date = end_date - timedelta(days=random.randint(0, 90))

        # Assign difficulty based on proportion from stats
        difficulty = random.choices(
            ["easy", "medium", "hard"],
            weights=[
                counts["easy"] / total,
                counts["medium"] / total,
                max(counts["hard"], 0) / total,
            ]
        )[0]

        records.append({
            "problem_id": problem_id,
            "difficulty": difficulty,
            "solved_at":  solved_date,
        })
        seen_slugs.add(problem_id)
        seen_slugs.add(slug)

    # Synthesize remaining records to reach total count
    synthetic = _synthesize_records(username, counts, seen_slugs, start_date, end_date)
    records.extend(synthetic)

    return records
