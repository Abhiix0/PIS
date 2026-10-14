# CLAUDE.md

Guidance for Claude Code in this repository. Verify files and commands against the repo before relying on them; do not assume they exist.

## Documents

- `PIS_PRD.md` — product specification (open decisions in §19).
- `PIS_PHASED_IMPLEMENTATION_PLAN.md` — engineering sequence and non-negotiable rules. Work one phase at a time; stop at the phase's exit gate.
- `docs/architecture/current-state.md` — verified description of today's system, known limitations, open decisions.

## Product and stack

Placement Intelligence System (PIS) scores student **placement-readiness** from coding (LeetCode) and GitHub activity plus CGPA. PostgreSQL 15 (SQL feature engineering) → FastAPI (`app/`) → Streamlit dashboard (`dashboard/`, pure HTTP client of the API, no DB access). Python 3.11, scikit-learn RandomForest, pandas, `psycopg2` only (no SQLAlchemy usage, although it is in `requirements.txt`) via one `ThreadedConnectionPool` in `ingest/db_connection.py`. Docker Compose: `db`, `api`, `dashboard`.

## Repository map

| Path | Role |
|---|---|
| `app/` | FastAPI app (`main.py` lifespan fails fast on DB/model problems), `schemas.py`, `routers/` (students, ingest, predictions, insights, features, pipeline, admin) |
| `services/pipeline.py` | Per-student orchestration: coding ingest → GitHub ingest → feature SQL → predict → insights |
| `ingest/` | `coding.py`/`github.py` (synthetic generators), `leetcode_api.py`/`github_api.py` (real APIs), `validators.py`, `db_connection.py` |
| `features/compute.py` | Runs feature SQL, loads, MinMax-scales, writes `models/scaler.pkl` and `features/*.csv` |
| `sql/` | `migrations/` (ordered; the only schema path, run by `python -m ingest.migrate`), `seed.sql` (demo data, local/test only), `feature_engineering.sql` (full table), `feature_engineering_single.sql` (per student), `ranking.sql` |
| `ml/` | `labels.py` (constructed labels), `train.py`, `predict.py` |
| `insights/` | `rules.py` (raw-value thresholds), `engine.py` (ranking by feature importance, composite patterns) |
| `dashboard/` | `app.py`, `api_client.py` (all HTTP calls live here) |
| `models/` | Committed `.pkl` artifacts + `feature_importances.json` (`models/staging/` used by retrain) |
| `tests/` | pytest; see below |
| `venv/` | Local virtualenv, git-ignored; ignore it |

## Commands

Verified by inspecting files unless marked **(ran)**.

```bash
cp .env.example .env            # DATABASE_URL required; GITHUB_TOKEN optional; AUTH_ISSUER/AUTH_AUDIENCE/AUTH_JWKS_URL required in staging/production
make up                         # docker-compose up --build (API :8000/docs, dashboard :8501)
make down | make down-clean     # stop | stop and wipe DB volume
make test                       # pytest inside api container (docker-compose exec)
make test-local                 # pytest tests/ -v --tb=short (needs live DB + models/)
make pipeline-all               # POST /pipeline/batch for students 1-8
make health | make logs | make seed
python -m features.compute && python -m ml.train && python -m ml.predict   # entrypoint.sh boot order, then uvicorn app.main:app
# No DB/models needed (23 passed, using venv/Scripts/python.exe -m pytest) (ran):
pytest tests/test_core.py tests/test_insights.py tests/test_github_api.py tests/test_leetcode_api.py
```

`make up`, `make test`, `make test-local`, and the module commands were **not** run in Phase 0 (no live DB). The system `python` on the dev machine lacks `psycopg2`; use `venv/Scripts/python.exe`.

## Execution flow

`POST /pipeline/{id}` (`app/routers/pipeline.py`, 5-minute cooldown unless `?force_refresh=true`) → `services/pipeline.run`: ingest coding and GitHub (real API if username set and 24h sync stale, otherwise synthetic) → `features.compute.run_feature_sql_for_student` → `ml.predict.predict` (scaler + RF regressor/classifier, upserts `predictions`, throttled `prediction_history`) → `insights.engine.InsightEngine`.

## Conventions

- Keep `sql/feature_engineering.sql` and `_single.sql` logic identical. Adding a feature touches SQL, `features/compute.py` (`SCALE_COLS`, scaler), `ml/labels.py`, `ml/train.py`, `ml/predict.py`, `insights/rules.py`, `schemas.py`, and the `features` table.
- Schema changes = a new numbered file in `sql/migrations/` (applied in filename order, recorded in `schema_migrations`; never edit an applied file). No other schema path exists. Config lives in `config.py` (`APP_ENV`, `validate()`).
- Dashboard calls go through `dashboard/api_client.py` only.
- Match surrounding style (psycopg2 `get_connection()` context manager, Pydantic schemas, flat routers). No wholesale rewrites.
- Tests: pytest, external HTTP mocked with `unittest.mock`; API tests (`test_api.py`, `test_pipeline.py`) hit a real DB migrated with `python -m ingest.migrate --seed`; `tests/test_migrate.py` DB tests need `TEST_ADMIN_DATABASE_URL` (a role that can CREATE DATABASE) and use a throwaway database. New logic gets a test; schema changes need a clean-database check.
- Workflow: inspect → plan → implement → test → review. Report only checks you actually ran.

## Mandatory safeguards

- **Synthetic data**: random generators exist in `ingest/coding.py`, `ingest/github.py`, and fall back silently in `services/pipeline.py` and `app/routers/ingest.py`. Never add new hidden fallbacks; synthetic data belongs only in labelled demo/test paths. Do not describe synthetic-derived results as the user's real activity.
- **Provenance**: `fetch_leetcode_data` builds per-problem rows from **aggregate** counts with invented dates (70% last-30-days cycle, 30% random 90 days). Never invent exact historical timestamps from aggregates; GitHub `commit_date` is `pushed_at` of the repo, not a commit date. Record the source of every datum.
- **ML claims**: labels are a weighted formula of the same features plus fixed-seed Gaussian noise (σ=5). The models learn that formula, not placement outcomes, on ~8 seed students. Never claim they predict hiring/placement; call the output a readiness *proxy score*. Any ML change needs documented baseline, experiment, and evaluation; promote models only after validation and smoke test with a rollback path.
- **Security**: `app/auth.py` verifies IdP-issued RS256 JWTs (see `docs/phase5/auth-architecture.md`); every route except `/health*` requires a token. Legacy `students`-keyed routes and `/admin/*` are operator-only (role claim `pis_operator`); user data lives in `profiles`, scoped by `user_id` in the SQL itself. Never expose one user's records via an identifier alone. Real-user ingestion stays disabled until Phase 6. staging/production refuse to start without AUTH_* settings.
- **Secrets**: never commit `.env`, tokens, or admin keys; never print them; never embed server secrets in any client bundle. The `Dockerfile` does `COPY . .` and there is no `.dockerignore`, so a local `.env` is copied into the image — do not push such images.
- Do not add an LLM, vector DB, queue, Redis, Kubernetes, microservices, or new model family without a written requirement and rationale.
