# Data-Source Feasibility Audit

Access date: 2026-10-13. "Code" = read from `ingest/*_api.py` in this repo. "Doc" = fetched from the cited page. "Unverified" = not confirmed in this review. No live API calls were made.

## 1. GitHub

| Item | Finding |
|---|---|
| Access | REST `api.github.com`. Works unauthenticated; token optional (code: `_headers`). |
| Limits | Doc ([rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)): unauthenticated 60 req/h per IP; PAT/OAuth user token 5,000 req/h; secondary limits (≤100 concurrent requests, 900 points/min REST). GitHub may change secondary limits without notice. A shared server IP serving many users exhausts 60/h quickly. A shared server token is a shared budget and a secret-handling risk (CLAUDE.md, FR-INT-002). |
| What the code collects | Code: `ingest/github_api.py` (`github-rest-v1`). Repos from `/users/{u}/repos` with `type=owner`, `sort=pushed`, forks dropped client-side, up to 3 pages of 100, then capped at `MAX_REPOS = 10` (most recently pushed first; truncation marks the run partial). For each repo, the **lifetime** count of commits with `author=<username>` (`_commit_count`: `per_page=1` plus the `Link` `rel="last"` page number; 409 = empty repo = 0). Also a `github_public_repo_count` observation. |
| Remaining limits for feature validity | The count is lifetime per repo, not windowed, so it is not an activity timeline. Attribution relies on GitHub matching the `author` filter to the account; unlinked-email loss is **unverified**. Repos outside the 10 most recently pushed owned repos, and org repos, are not counted. The earlier version (no author filter, `type=all`, forks included) is superseded; the all-committers defect no longer applies to the current code. Effect sizes not measured. |
| `event_at` | Set to the repo's `pushed_at` with `event_at_precision = repo_push` (`unknown` if absent). That is a repo-level timestamp, not a commit date. Time-window features built on it are not a valid activity timeline. |
| Historical activity | **Observable** if collected properly. List-commits supports `author`, `since`, `until`, 100 per page ([commits docs](https://docs.github.com/en/enterprise-server@3.21/rest/commits/commits); that is the Enterprise Server page, so github.com behaviour is unverified). Commits made under an email not linked to the account are likely not attributed (unverified). The contributor-stats endpoint gives weekly commits per contributor but may answer 202 while computing, and zeroes additions/deletions on repos with ≥10,000 commits (from a search summary of the docs; verify). |
| Not observable | Private repos (without OAuth), commits under unlinked emails, code quality, review activity, work outside GitHub. Squash-merges hide commit counts. |
| Must stay unavailable | Per-day activity before collection, inferred from aggregates. Student-authored commit counts when only repo totals were fetched. Private activity under a public-only connection. |
| Failure behaviour | Code maps 404 to `not_found`, rate limits to `rate_limited`, 401/403 to `forbidden`, other failures to `unavailable`/`malformed`, and raises `ProviderError`; timeouts/5xx get 3 bounded attempts. If every per-repo lookup fails the run fails; partial failures set `partial`. No synthetic fallback in this adapter. Behaviour against live GitHub not exercised here (unverified). |
| Terms / retention | GitHub ToS and API terms not reviewed in this review. **Open item.** |
| Feature suitability | Lifetime authored commits per repo (current) is usable as a labelled aggregate. Active weeks, recency of last authored commit and windowed counts need dated commits, which the current collector does not fetch (cost ≥1 request per repo per page). See `docs/ml/experiment-protocol.md` §B for the proposed GraphQL collector (unverified). |

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
| GitHub per-repo lifetime authored commits (`author` filter) | observed; attribution loss for unlinked emails unverified |
| GitHub author-filtered commit timestamps | observable, not currently collected |
| CGPA | user-entered, unverified |
| `ingest/coding.py`, `ingest/github.py`, `seed.sql` | synthetic fixtures |
| `features/*.csv`, models, labels | derived; labels are constructed |

## 4. Consequences

1. Of the five current features, only `total_problems`, `avg_difficulty` (aggregate) and `cgpa` (user-entered) are defensible as-is. `consistency_score` is fabricated for real LeetCode users. `commit_frequency` is dated by repo `pushed_at` (precision `repo_push`), not by commit; its author attribution depends on the unverified `author` match.
2. A reliable time series exists only for GitHub (re-collected properly) and for PIS's own future snapshots.
3. No source provides placement outcomes.

## 5. Open items (not done in this review)

- Read the LeetCode and GitHub terms.
- Verify author-matching and unlinked-email loss on a real account.
- Measure request cost per user.

These need a human, or a later review with network access to real accounts.
