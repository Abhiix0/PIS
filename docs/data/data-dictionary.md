# Feature data contract — `features-v1`

Version constant: `features.compute.FEATURE_SCHEMA_VERSION`. Bump it (and this file) when a feature's SQL, unit, window or scaling changes. A test fails if a scaled feature is missing from this file.

SQL source of truth: `sql/feature_engineering.sql` (cohort) and `sql/feature_engineering_single.sql` (one student). They must stay logically identical; `tests/test_migrate.py::test_full_and_single_feature_sql_agree` is the parity test.

**Scope.** These features are computed from the legacy `students`-keyed tables (`coding_activity`, `github_activity`), which hold **demo/synthetic** data and, for GitHub only, repo-level observed aggregates. Real users' provider data lives in `source_observations` and is **not yet an input to any feature**: building real-user snapshots is snapshot work. Until then no real-user assessment exists.

**Provenance.** Each legacy activity row carries `provenance` (`synthetic` by default; `observed` only for rows written from the GitHub adapter). A feature's provenance is the weakest provenance of its input rows. Features are not yet stored with a provenance column (`features` table unchanged); that is a snapshot concern.

**Missing-value semantics (all features, known defect).** The SQL `COALESCE`s a missing input to `0`, so "no data" and "measured zero" are indistinguishable in `features`. Do not read a `0` as an observation. `source_observations.value_state` is the model that separates them (`measured_zero` vs `not_collected` / `source_failed`); the feature tables do not use it yet.

| Feature | Definition | Unit | Source fields | Window | Formula | Missing → | Quality requirements | Provenance rule |
|---|---|---|---|---|---|---|---|---|
| `cgpa` | Student-entered CGPA | grade points, 0–10 | `students.cgpa` | none (point value) | copied | row must exist (NOT NULL for scaling) | `CHECK 0..10` | `user_entered` |
| `total_problems` | Count of coding-activity rows | problems | `coding_activity.id` | all time | `COUNT(*)` per student | 0 | unique `(student_id, problem_id)`; `solved_at` ≤ today | `synthetic` for all current rows. **Never** populated from LeetCode (aggregate counts have no per-problem rows). |
| `avg_difficulty` | Mean difficulty weight | 1 (easy) – 3 (hard) | `coding_activity.difficulty` | all time | `ROUND(AVG(easy=1, medium=2, hard=3), 2)` | 0.0 | difficulty in the 3 allowed values | `synthetic` |
| `consistency_score` | Share of the last 13 weeks with at least one solve | 0–1 | `coding_activity.solved_at` | last 90 days | `LEAST(COUNT(DISTINCT date_trunc('week', solved_at)) / 13, 1)` | 0.0 | needs real solve dates. **Not computable for real LeetCode users**: dates are unobservable. | `synthetic` only |
| `commit_frequency` | Commits per day since the earliest recorded repo push date | commits/day | `github_activity.commits`, `commit_date` | earliest `commit_date` → today | `SUM(commits) / NULLIF(CURRENT_DATE - MIN(commit_date), 0)` | 0.0 | `commits > 0`; `commit_date` ≤ today | `observed` (GitHub adapter) or `synthetic` |

## What `commit_frequency` does and does not mean

- `commits` is the number of commits **authored by the username** in a public, non-fork repo (adapter uses `author=<username>`; commits under an email not linked to the account are not counted). It is a repo total, not a daily history.
- `commit_date` is the repo's **last push date** (`pushed_at`), not a commit date. Dividing a lifetime total by "days since the oldest last-push" is therefore not a verified daily rate. Treat it as a coarse activity proxy. It is kept so the demo model keeps working; redefining it is a snapshot-design decision.
- Capped at the 10 most recently pushed non-fork repos.

## Observation types (`source_observations.observation_type`)

| Type | Provider | Meaning | Granularity | `event_at` | Notes |
|---|---|---|---|---|---|
| `github_public_repo_count` | github | Public non-fork repos enumerated (≤ 10) | aggregate | NULL | `measured_zero` for an account with none. Truncated at the cap ⇒ run is `partial`. |
| `github_repo_commit_count` | github | Commits by the user in one repo | aggregate | repo `pushed_at`, precision `repo_push` | `source_object_id` = repo name. |
| `github_contribution_day` | github | Contribution count for one UTC day from GitHub's `contributionCalendar` (GraphQL) | event | the date at 00:00 UTC, precision `day` | `source_object_id` = ISO date. A reported 0 is `measured_zero`; a day GitHub does not return is absent, never zero. Last 365 UTC days incl. today; fewer days returned ⇒ run is `partial`. Off unless `GITHUB_CALENDAR_ENABLED=true` and a server `GITHUB_TOKEN` is set. Whether private-repo contributions are included depends on the user's profile setting: unverified for third-party users (spike). Not yet an input to any feature. |
| `leetcode_solved_easy/medium/hard` | leetcode | Accepted-problem count by difficulty at fetch time | aggregate | NULL (precision `unknown`) | Disabled by default (`LEETCODE_INTEGRATION_ENABLED`). Time = `collected_at` only. |

Ingestion/parser version: `services.sync.INGESTION_VERSION` on each `sync_runs` row; adapter payload version on each observation (`payload_version`).
