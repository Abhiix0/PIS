# CLAUDE.md

Guidance for Claude Code in this repository. Verify files and commands against the repo before relying on them; do not assume they exist.

## Documents

- `docs/README.md` — index of all documentation (topical folders: architecture, data, ml, security, ops, research, design, product, history).
- `docs/architecture/current-state.md` — verified description of today's system, known limitations, open decisions.
- `docs/product/PIS_PRD.md` — product specification (open decisions in §19). The implementation plan was deleted; `docs/history/` is historical.
- `CONTRIBUTING.md` — branching, `make check`, migration/synthetic-data/ML rules.

## Product and stack

Placement Intelligence System (PIS) scores student **placement-readiness** from coding (LeetCode) and GitHub activity plus CGPA. PostgreSQL 15 (SQL feature engineering) → FastAPI (`app/`) → the desktop client (`apps/desktop/`, HTTP client of `/api/v1`). Python 3.11, scikit-learn RandomForest, pandas, `psycopg2` only (no SQLAlchemy usage, although it is in `requirements.txt`) via one `ThreadedConnectionPool` in `ingest/db_connection.py`. Docker Compose: `db`, `api`.

## Repository map

| Path | Role |
|---|---|
| `app/` | FastAPI app (`main.py` lifespan fails fast on DB/model problems), `routers/v1.py` (`/api/v1/*` + `/auth/logout`), `routers/admin.py` (operator). Route table: `docs/architecture/api-surface.md`; all errors use one `{error:{code,message,request_id}}` envelope |
| `services/sync.py` | Real-user sync lifecycle (`sync_runs`, `source_observations`, quarantine); routes in `app/routers/v1.py` |
| `services/privacy.py` | Export, account deletion, audit events |
| `ingest/` | `leetcode_api.py`/`github_api.py` (provider adapters -> typed `Observation`, raise `ProviderError`; `provider.py`), `validators.py`, `db_connection.py` (`get_connection`, `fetch_all` for read-only dict queries) |
| `features/compute.py` | Runs feature SQL, loads, MinMax-scales, writes `models/scaler.pkl` and `features/*.csv` |
| `sql/` | `migrations/` (ordered; the only schema path, run by `python -m ingest.migrate`), `seed.sql` (demo data, local/test only), `feature_engineering.sql` (full table) |
| `ml/` | `labels.py` (constructed labels), `train.py`, `bundle.py` (registry; `bootstrap` = local-only activation as `local-bootstrap`), `predict.py` (batch, boot-time) |
| `models/` | `bundles/<version>/` (immutable model bundles, registry in `model_versions`; `ml/bundle.py`), `staging/` for training output. Legacy top-level `.pkl` are unused |
| `tests/` | pytest; see below |
| `venv/` | Local virtualenv, git-ignored; ignore it |

## Commands

Verified by inspecting files unless marked **(ran)**.

```bash
cp .env.example .env            # DATABASE_URL required; GITHUB_TOKEN optional; AUTH_ISSUER/AUTH_AUDIENCE/AUTH_JWKS_URL required in staging/production
make up                         # docker-compose up --build (API :8000/docs)
make down | make down-clean     # stop | stop and wipe DB volume
make test                       # pytest inside api container (docker-compose exec)
make test-local                 # pytest tests/ -v --tb=short (needs live DB + models/)
make health | make logs
python -m features.compute && python -m ml.train && python -m ml.bundle bootstrap && python -m ml.predict   # entrypoint.sh boot order (train makes a candidate; activate via ml.bundle), then uvicorn app.main:app
# No DB/models needed:
pytest tests/test_core.py tests/test_github_api.py tests/test_leetcode_api.py tests/test_config.py tests/test_route_coverage.py
make check                      # lint + mypy + pytest with coverage floor (needs DB and TEST_ADMIN_DATABASE_URL, a role that can CREATE DATABASE)
```

Make targets take the interpreter via `make PY=<path-to-venv-python> ...` (default `python`, which may lack `psycopg2`). With `TEST_ADMIN_DATABASE_URL` set, the test session builds its own migrated, seeded throwaway database. `docs/architecture/audit-report.md` lists what was last run (Phase 1b: 277 backend tests, coverage 82.50%; desktop 55 tests) and what was never verified (Docker, Tauri, Terraform, remote CI, live IdP).

Real users get `insufficient_evidence` from `POST /api/v1/assessments`, never a score. The GitHub daily-calendar collector is off unless `GITHUB_CALENDAR_ENABLED=true` (default `false`, needs `GITHUB_TOKEN`).

## Execution flow

Real users: `PUT /api/v1/integrations/{provider}` → `POST .../sync` (202, background `services.sync.execute_run`) → `source_observations` → `POST /api/v1/assessments` snapshots evidence (`insufficient_evidence`, no score). Operators: `/admin/retrain` → candidate bundle → approve → activate. Boot (`entrypoint.sh`, local only): migrate → `features.compute` → `ml.train` → `ml.bundle bootstrap` → `ml.predict`.

## Conventions

- Adding a feature touches `sql/feature_engineering.sql`, `features/compute.py` (`SCALE_COLS`, scaler), `ml/labels.py`, `ml/train.py`, `ml/predict.py`, and the `features` table.
- Schema changes = a new numbered file in `sql/migrations/` (applied in filename order, recorded in `schema_migrations`; never edit an applied file). No other schema path exists. Config lives in `config.py` (`APP_ENV`, `validate()`).
- A new route needs a row in `docs/architecture/api-surface.md` (a test compares it to `app.routes`) and a test.
- Match surrounding style (psycopg2 `get_connection()` context manager, Pydantic schemas, flat routers). No wholesale rewrites.
- Tests: pytest, external HTTP mocked with `unittest.mock`; API tests (`test_api_v1.py`, `test_sync.py`, `test_auth.py`) hit a real DB migrated with `python -m ingest.migrate --seed`; `tests/test_migrate.py` DB tests need `TEST_ADMIN_DATABASE_URL` (a role that can CREATE DATABASE) and use a throwaway database. New logic gets a test; schema changes need a clean-database check.
- Workflow: inspect → plan → implement → test → review. Report only checks you actually ran.

## Mandatory safeguards

- **Synthetic data**: the random generators were removed; the only synthetic data is `sql/seed.sql` (local/test), and the `provenance` column on `coding_activity`/`github_activity` defaults to `synthetic`. A failed provider call never falls back to synthetic data. Never add hidden fallbacks; synthetic data belongs only in labelled demo/test paths. Do not describe synthetic-derived results as the user's real activity.
- **Provenance**: real-user provider data is stored only as `source_observations` (migration 005) with `provenance`, `granularity`, `event_at_precision`, and a `sync_run_id`; LeetCode is aggregate-only (no solve dates, disabled unless `LEETCODE_INTEGRATION_ENABLED`). Never invent exact timestamps from aggregates; GitHub `commit_date`/`event_at` is the repo's `pushed_at` (precision `repo_push`), not a commit date. Record the source of every datum. Feature definitions: `docs/data/data-dictionary.md`.
- **ML claims**: labels are a weighted formula of the same features plus fixed-seed Gaussian noise (σ=5). The models learn that formula, not placement outcomes, on ~8 seed students. Never claim they predict hiring/placement; call the output a readiness *proxy score*. Any ML change needs documented baseline, experiment, and evaluation; promote models only after validation and smoke test with a rollback path.
- **Security**: `app/auth.py` verifies IdP-issued RS256 JWTs (see `docs/security/auth-architecture.md`); every route except `/health*` requires a token. `/admin/*` is operator-only (role claim `pis_operator`); user data lives in `profiles`, scoped by `user_id` in the SQL itself. Never expose one user's records via an identifier alone. Real-user ingestion runs only through `/api/v1/integrations/*` (owner-scoped, public usernames, per-connection cooldown; see `docs/data/provenance.md`). staging/production refuse to start without AUTH_* settings.
- **Secrets**: never commit `.env`, tokens, or admin keys; never print them; never embed server secrets in any client bundle. The `Dockerfile` does `COPY . .`; `.dockerignore` excludes `.env`, but do not push images built from a tree with other local secrets.
- Do not add an LLM, vector DB, queue, Redis, Kubernetes, microservices, or new model family without a written requirement and rationale.
