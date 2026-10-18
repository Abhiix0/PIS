# Data-Source Feasibility Audit

Access date: 2026-10-13. "Code" = read from `ingest/*_api.py` in this repo. "Doc" = fetched from the cited page. "Unverified" = not confirmed in this review. No live API calls were made.

## 1. GitHub

| Item | Finding |
|---|---|
| Access | REST `api.github.com`. Works unauthenticated; token optional (code: `_get_headers`). |
| Limits | Doc ([rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)): unauthenticated 60 req/h per IP; PAT/OAuth user token 5,000 req/h; secondary limits (≤100 concurrent requests, 900 points/min REST). GitHub may change secondary limits without notice. A shared server IP serving many users exhausts 60/h quickly. A shared server token is a shared budget and a secret-handling risk (CLAUDE.md, FR-INT-002). |
| What the code collects | ≤10 most recently updated repos (`type=all`, so forks and other orgs included). For each repo, the **total commit count** via the `Link` header trick with **no author filter** (`_get_repo_commit_count`). |
| Defect for feature validity | That count is all committers' commits, not the student's. A fork or team repo inflates "student commits". Verified from code; effect size not measured. |
| `commit_date` | Set to the repo's `pushed_at` (code). That is a repo-level timestamp, not a commit date. Time-window features built on it are not a valid activity timeline. |
| Historical activity | **Observable** if collected properly. List-commits supports `author`, `since`, `until`, 100 per page ([commits docs](https://docs.github.com/en/enterprise-server@3.21/rest/commits/commits); that is the Enterprise Server page, so github.com behaviour is unverified). Commits made under an email not linked to the account are likely not attributed (unverified). The contributor-stats endpoint gives weekly commits per contributor but may answer 202 while computing, and zeroes additions/deletions on repos with ≥10,000 commits (from a search summary of the docs; verify). |
| Not observable | Private repos (without OAuth), commits under unlinked emails, code quality, review activity, work outside GitHub. Squash-merges hide commit counts. |
| Must stay unavailable | Per-day activity before collection, inferred from aggregates. Student-authored commit counts when only repo totals were fetched. Private activity under a public-only connection. |
| Failure behaviour required | Distinguish 404 (no such user), empty profile, rate limit, and network error. The current silent synthetic fallback (D-03) must go. |
| Terms / retention | GitHub ToS and API terms not reviewed in this review. **Open item.** |
| Feature suitability | Suitable with author-filtered queries: active weeks, recency of last authored commit, repo/language breadth, authored commits in a window (cost ≥1 request per repo per page). Not suitable: "total commits per repo" as currently defined. |

## 2. LeetCode

| Item | Finding |
|---|---|
| Access | Unofficial `https://leetcode.com/graphql`; no authentication in code. Web search found no official public API or schema; third-party projects describe it as unofficial. |
| Terms | The LeetCode ToS fetch returned HTTP 403, so **terms on automated access are unverified**. Treat the integration as possibly not permitted until a human reads the ToS (PRD §19 #4, FR-INT-003). |
| What the code collects | One query: `matchedUser.submitStats.acSubmissionNum`, i.e. solved counts by difficulty (aggregate) at call time. A code comment says `recentSubmissionList` was removed as unsupported. |
| Defect | `fetch_leetcode_data` then generates one row per solved problem with invented IDs and **invented dates** (70% in the last 30 days, 30% random within 90 days). Synthetic timestamps are stored beside observed counts (D-15). `consistency_score` and any recency feature derived from them are **fabricated for real users**. |
| Historical activity | Not observable from this query. Whether a submission calendar or recent-AC list is exposed and stable is **unverified**. Even if it is, it is an unofficial interface that can change. |
| Reliability | Unofficial GraphQL can change or be blocked without notice (hypothesis; consistent with the removed-field comment). Rate limits undocumented. |
| Observed | Totals by difficulty at fetch time. Per-problem IDs, topics, tags, and dates are not collected. |
| Must stay unavailable | Solve dates, streaks, consistency, topic coverage, and difficulty mix over time, unless a separately verified source provides them. |
| Feature suitability | Suitable: total solved and difficulty mix (aggregate, labelled with fetch time). A longitudinal signal exists only if PIS snapshots the aggregates itself; each snapshot is a real observation dated at collection. Not suitable: consistency, recency, weekly activity. |

## 3. Observed vs aggregate vs estimate vs synthetic

| Datum | Class |
|---|---|
| LeetCode solved counts by difficulty | aggregate, observed at fetch time |
| LeetCode per-problem rows and `solved_at` | **synthetic** (current code) |
| GitHub repo list, `pushed_at` | observed (repo-level) |
| GitHub per-repo total commits | observed, not user-attributed |
| GitHub author-filtered commit timestamps | observable, not currently collected |
| CGPA | user-entered, unverified |
| `ingest/coding.py`, `ingest/github.py`, `seed.sql` | synthetic fixtures |
| `features/*.csv`, models, labels | derived; labels are constructed |

## 4. Consequences

1. Of the five current features, only `total_problems`, `avg_difficulty` (aggregate) and `cgpa` (user-entered) are defensible as-is. `consistency_score` is fabricated for real LeetCode users. `commit_frequency` is mis-attributed and mis-dated.
2. A reliable time series exists only for GitHub (re-collected properly) and for PIS's own future snapshots.
3. No source provides placement outcomes.

## 5. Open items (not done in this review)

- Read the LeetCode and GitHub terms.
- Verify author-matching and unlinked-email loss on a real account.
- Measure request cost per user.

These need a human, or a later review with network access to real accounts.
