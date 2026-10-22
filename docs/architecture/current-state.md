# NexGauge current state

Description of the repository on branch `revamp`, written from the source. **Verified** = read in code. **Unverified** = inferred, or depends on running the stack, which this document did not do. Route list: `api-surface.md`. Limits and open decisions are at the end.

## 1. Topology

- `docker-compose.yml`: `db` (postgres:15-alpine, healthcheck) and `api` (built from `Dockerfile`, runs `entrypoint.sh`, mounts `./models` and `./features`). There is no dashboard service. Verified.
- Desktop client: `apps/desktop/` (Tauri 2 + React + TypeScript), an HTTP client of `/api/v1`. See `../design/desktop.md`.
- Infra for a hosted deployment: `deploy/aws/` (`main.tf`, `release.sh`), `../architecture/decisions/0004-aws-hosting.md`, `../ops/runbook.md`. Never applied to a real account (unverified).
- CI: `.github/workflows/{backend,desktop,release}.yml` exist; their run results are not known here (unverified).

## 2. Configuration (`config.py`)

`APP_ENV` is `local|test|staging|production`. `validate()` returns errors; in staging/production it additionally requires `AUTH_ISSUER`, `AUTH_AUDIENCE`, `AUTH_JWKS_URL` and rejects placeholder DB passwords. `seed_allowed()` is false when deployed. `LEETCODE_INTEGRATION_ENABLED` defaults to false. `SYNC_COOLDOWN_SECONDS` defaults to 300. Request bodies are capped at 64 KiB. Verified.

## 3. Database and migrations

`python -m ingest.migrate [--seed]` applies `sql/migrations/*.sql` in filename order and records each in `schema_migrations`. The API refuses to start while migrations are pending. Verified (`app/main.py` lifespan, `ingest/migrate.py`).

| Migration | Adds |
|---|---|
| 000_baseline | `students`, `coding_activity`, `github_activity`, `features`, `predictions`, indexes |
| 001_add_github_unique | unique `github_activity` key (dedupes first) |
| 001_add_usernames | `students.github_username`, `leetcode_username` (duplicate prefix is allowed once; see `sql/migrations/README.md`) |
| 002_add_sync_timestamps | `*_last_synced` on `students` |
| 003_add_prediction_history | `prediction_history` |
| 004_users_profiles | `users`, `profiles`, enum `data_origin` |
| 005_ingestion_provenance | enums `provenance`, `value_state`; `provenance` column on legacy activity tables; `integration_connections`, `sync_runs`, `source_observations`, `data_quality_results` |
| 006_model_versions | `model_versions` (one `active` row, partial unique index); assessment columns on `predictions`/`prediction_history`; history immutability trigger |
| 007_assessments_data_requests | `assessments` (immutable by trigger), `data_requests` |
| 008_privacy_audit | `audit_events` (immutable by trigger), `users.research_consent_at` |

The legacy `students`-keyed tables (000-003) still exist. They hold only demo data from `sql/seed.sql` (8 students, `provenance = synthetic`) and feed the feature/training path. Real users live in `users`/`profiles`. Verified.

## 4. Authentication and authorization (`app/auth.py`)

- The API only verifies tokens: RS256 JWT, signature via JWKS (`AUTH_JWKS_URL`), `iss`, `aud`, `exp`, `iat`, `sub` required. If any `AUTH_*` value is unset every protected route returns 401.
- A valid token get-or-creates a `users` row; non-`active` users get 403; tokens issued before `sessions_valid_after` are rejected (logout / deletion revoke sessions).
- Operator = role `pis_operator` inside the claim named by `AUTH_ROLE_CLAIM` (default `pis_roles`).
- Rate limits are in-process per worker (`rate_limit`, `expensive` = 10/min); failed auth is limited per client IP. Not shared across replicas.
- Every route except `/health*` needs a token. User queries filter by the token's `user_id` in SQL. Verified. Design: `../security/auth-architecture.md`.

## 5. Real-user data flow

1. `PUT /api/v1/integrations/{provider}` stores a public username (owner-scoped, `services/sync.py::connect`). LeetCode is refused unless `LEETCODE_INTEGRATION_ENABLED`.
2. `POST /api/v1/integrations/{provider}/sync` creates a `sync_runs` row before calling the provider, returns 202, then `execute_run` runs in the background. Per-connection cooldown counts failed attempts; one running sync per connection (unique index); runs older than 15 minutes count as dead.
3. `ingest/github_api.py` and `ingest/leetcode_api.py` return typed `Observation`s or raise `ProviderError`; `validate_observation` runs before storage. Results are appended to `source_observations` with `provenance`, `granularity`, `event_at_precision`, `sync_run_id`. A failed sync never writes synthetic data and never replaces earlier observations.
4. `GET /api/v1/me/data-quality`, `/sync-runs` expose run state.
5. `POST /api/v1/assessments` snapshots current evidence and always stores `assessment_type = insufficient_evidence` with no score (`app/routers/v1.py::create_assessment`). Real-user observations do **not** feed `features`, `predictions` or the model. Verified.

Provenance rules: `../data/provenance.md`. Privacy export/deletion/audit: `services/privacy.py`, `../data/privacy-and-retention.md`.

## 6. Features, training, model bundles

- `sql/feature_engineering.sql` computes five features for the legacy tables; `python -m features.compute` loads them, MinMax-scales, writes `models/scaler.pkl` and `features/*.csv`. Definitions: `../data/data-dictionary.md`.
- `ml/labels.py`: label = weighted sum of the same scaled features plus fixed-seed Gaussian noise (σ=5); categories by score threshold. `ml/train.py` trains a RandomForest regressor and classifier into a staging directory. The model learns this constructed formula, not placement outcomes, from ~8 seed rows. Verified in code.
- `ml/bundle.py`: immutable bundles `models/bundles/<version>/` with a manifest of file checksums, feature order and schema version; registry in `model_versions`; lifecycle candidate -> approved -> active -> retired, one active at a time, rollback to the last retired. Startup loads the active bundle and refuses checksum or schema mismatch; with none active the API does not start. Details: `../ml/model-lifecycle.md`.
- `ml/predict.py` is the batch scorer over the legacy `students`/`features` tables, used at local boot.
- `ml/experiment.py` (`python -m ml.experiment`) is the baseline runner; see `../ml/experiment-protocol.md`, `../ml/baseline-report.md`.
- The former `insights/` rule engine and Streamlit `dashboard/` are not in git (only untracked `__pycache__` remains locally). `../ml/model-lifecycle.md` still names `insights/`; treat that sentence as stale.

## 7. Boot paths

- Local/compose (`entrypoint.sh`): migrate (+ `--seed` when `SEED_DEMO_DATA=true`) -> `features.compute` -> `ml.train` -> `ml.bundle bootstrap` (activates the newest candidate as `local-bootstrap` only if none is active) -> `ml.predict` -> uvicorn.
- staging/production: uvicorn only. Migrations are a separate release step; models ship in the image. Verified in the script; never executed against a deployed environment.

## 8. API

`app/main.py` mounts `routers/admin.py`, `routers/v1.py` (`/api/v1/*`) and `session_router` (`/auth/logout`), plus `/health`, `/health/ready`, `/health/detailed`. All errors use `{error:{code,message,request_id}}`. Route table: `api-surface.md`; narrative: `api-v1.md`. A test (`tests/test_route_coverage.py`) compares the table with `app.routes`.

## 9. Tests

`tests/` is pytest. DB-free: `test_core`, `test_github_api`, `test_leetcode_api`, `test_config`, `test_ingestion_contracts`, `test_experiment`, `test_bundle` (mixed), `test_route_coverage`. DB-backed: `test_api_v1`, `test_sync`, `test_auth`, `test_ops`, `test_migrate` (needs `TEST_ADMIN_DATABASE_URL`). Results of the last run are recorded in the pull request or CI, not here.

## 10. Known limitations

- Scores are a readiness *proxy* from a constructed formula; no placement-outcome labels exist.
- No real-user score is produced yet (see §5.5).
- GitHub `commit_date`/`event_at` is the repo's `pushed_at`; LeetCode is aggregate-only.
- Legacy `students` tables, the scaler fit on all rows, and the feature SQL are still demo-scale (8 rows).
- Rate limiting is per process.
- `sqlalchemy` is listed in `requirements.txt` but the code uses `psycopg2` only (grep not exhaustive, unverified).
- The `Dockerfile` has `COPY . .`; `.dockerignore` excludes `.env`, `venv/` and `.env.*` (read, image not built).
- Stack boot (`make up`) end to end, the AWS deployment, signed installers and clean-machine installs are unverified.

## 11. Open decisions

See PRD §19 in `../product/PIS_PRD.md`: assessment target (outcome vs. preparation), GitHub access scope, LeetCode source and terms, which academic data is required, research consent, release channel.
