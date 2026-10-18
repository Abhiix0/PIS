# Ingestion, provenance, data quality

## Decisions taken (conservative defaults; PRD §19 #3 and #4 are still formally open)

| Decision | Chosen | Why / how to change |
|---|---|---|
| GitHub access (§19 #3) | **Public username lookup only.** No user tokens, no OAuth, nothing secret stored. | Delegated access needs a public-client flow (device/PKCE) and a secret-store design; neither exists. Adding it later means a new `connection` auth mode, not a schema rewrite. The optional server `GITHUB_TOKEN` only raises the shared rate budget and is never sent to clients. |
| LeetCode (§19 #4) | **Adapter built, disabled by default** (`LEETCODE_INTEGRATION_ENABLED=false`). Endpoints answer 503. | Unofficial GraphQL; terms unverified (research doc: ToS fetch returned 403). Enable only after a human clears the terms. When enabled it stores three solved-count aggregates and nothing else. |

## What changed

- **Adapters** (`ingest/github_api.py`, `ingest/leetcode_api.py`) return typed `Observation`s or raise `ProviderError(code)`; codes: `not_found, rate_limited, forbidden, unavailable, malformed, disabled`. Bounded retry (3 attempts, exponential backoff) on timeouts and 5xx only; rate limits are reported with `Retry-After`, never retried. Usernames are regex-checked before use (GitHub: URL path; LeetCode: now a GraphQL variable, not string-interpolated).
- **Removed fabrication:** `fetch_leetcode_data` (invented IDs and dates), the `commit_count = 1` fallback on failed repo lookups, the silent synthetic fallback on provider failure (`services/pipeline.py`, `/ingest/*/real`), and the destructive `clear_coding_activity`. `POST /ingest/coding/real/{id}` now returns 501.
- **Sync lifecycle** (`services/sync.py`): `sync_runs` row committed *before* the provider call → `running` → `succeeded | partial | failed` with counts and a safe error code. A DB unique index allows one running sync per connection; running rows older than 15 min are marked `failed/abandoned`; cooldown (`SYNC_COOLDOWN_SECONDS`, default 300) counts failed attempts too. Observations are append-only, so a failed or partial sync cannot overwrite or clear earlier data.
- **Empty vs failed:** an account with no repos stores `github_public_repo_count = 0` (`measured_zero`); a failed request stores nothing and the run is `failed` with a code. If every per-repo lookup fails, the whole run fails.
- **Validation/quarantine** (`ingest/validators.py::validate_observation`): type allow-list, finite non-negative integer within range, repo id present, aggregate cannot claim an exact time, `event_at` tz-aware, not future, not before 2008, precision requires a timestamp. Rejected records go to `data_quality_results` with a rule code and reason; they are never stored as values. Duplicates in one run are rejected (`uq_obs_per_run`).
- **Schema invariants** (migration 005, tested): `observed` requires a `sync_run_id`; `synthetic` forbids one; `measured_zero` ⇒ 0; present value ⇒ number; aggregate ⇒ no `exact` precision.
- **API** (owner-scoped by `user_id` in the SQL; other users get 404/empty): `GET /integrations`, `PUT /integrations/{github|leetcode}` `{username}`, `POST /integrations/{provider}/sync` (rate-limited), `GET /integrations/{provider}/sync-runs?limit=`. A failed provider call is a `200` run with `status=failed`; refusals are 404 (no connection), 409 (no profile / already running), 429 + `Retry-After` (cooldown), 503 (LeetCode disabled), 422 (bad username).
- **Legacy `students` path:** activity rows carry `provenance` (default `synthetic`, `observed` for GitHub adapter rows). `students` with a `leetcode_username` no longer get any coding rows; the pipeline step reports `skipped`. Synthetic generation runs only for students with no username.
- **Feature contract:** `docs/data/data-dictionary.md`, version `features-v1` (`FEATURE_SCHEMA_VERSION`). Full-vs-single SQL parity test already exists (`tests/test_migrate.py`).

## Integration limitations (honest list)

- GitHub: public, non-fork repos only; newest-pushed 10; attributed commits exclude commits under unlinked emails; no per-day history. `commit_frequency` is a coarse proxy (see data dictionary).
- Unauthenticated GitHub allows 60 requests/hour per server IP; one sync costs up to 1 + 10 + listing pages. Many users on one IP will hit `rate_limited`. A server token raises this to 5,000/h but is a shared budget.
- Changing a connected username disconnects the old connection and starts a new one; old observations remain, traceable via `sync_run → connection`.
- Cooldown/rate limit state for the API limiter is per process (unchanged from Phase 5). The running-sync guard is DB-enforced.

## Not done (out of scope for this phase)

- **Real-user features/assessments:** `source_observations` do not yet feed `features`, predictions or insights (Phase 7+/snapshots). The legacy `features` table still conflates "no data" with 0 and has no provenance column. Therefore "every assessment input traceable to provenance" holds for legacy inputs (row-level `provenance`) and for real observations, but there is no real-user assessment yet.
- Delegated GitHub access, user-entered CGPA as an observation, observation-read API, background worker/scheduler, stale-data (`value_state='stale'`) marking, dashboard changes (it still labels any username-bearing student "Real Data").
- No live-network test against GitHub or LeetCode was run; all provider behavior is verified against mocked responses only.
