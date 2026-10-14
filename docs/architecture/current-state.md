# PIS Current State (Phase 0)

Snapshot of the repo at `main` (commit `82b072d`), from reading the source. **Verified** = read in code. **Ran** = executed. **Unverified** = inferred or not executed. Only the four mock-based test files were run (23 passed); the stack was never started and no DB-backed test was run.

## 1. Topology

`docker-compose.yml`: `db` (postgres:15-alpine), `api` (built from `Dockerfile`, runs `entrypoint.sh`), `dashboard` (Streamlit, `API_URL=http://api:8000`). The `api` container mounts `./models` and `./features` from the host. Verified.

## 2. Database initialization

- **Updated in Phase 3.** The `db` container no longer runs init scripts. `entrypoint.sh` runs `python -m ingest.migrate` (plus `--seed` when `SEED_DEMO_DATA=true`, compose default, refused when `APP_ENV` is staging/production) before features/training. The API also refuses to start if migrations are pending.
- Tables: `students`, `coding_activity` (unique `(student_id, problem_id)`), `github_activity`, `features`, `predictions`, `prediction_history`. Migrations: 000 baseline, 001 github unique, 001 usernames, 002 sync timestamps, 003 history (`sql/migrations/`, tracked in `schema_migrations`).
- Resolved in Phase 3: `uq_github_activity` is applied by migration `001_add_github_unique.sql` (dedupes first); the non-immutable partial index was replaced by `idx_coding_student_date`. See `docs/phase3/stabilization-report.md`.
- Seed: 8 hand-written students (`aryan@pis.dev` etc.) with fixed-date activity rows. Verified.
- `features` has no `cgpa` column; CGPA is joined from `students` at load/predict time.

## 3. Request flow

`app/main.py` registers routers: students, ingest, predictions, insights, features (`/features`), pipeline, admin. The lifespan hook raises if `DATABASE_URL` is missing, the DB is unreachable, or any of `models/{regressor,classifier,scaler}.pkl` / `feature_importances.json` is missing; a short `ADMIN_KEY` only logs a warning. A global handler returns `Internal server error: <ExceptionType>`. A middleware logs method/path/status/duration.

Main path, `POST /pipeline/{id}[?force_refresh=true]`:
1. Router checks the student exists, then returns **429** if `features.computed_at` is under 5 minutes old (unless forced).
2. `services/pipeline.run` reads usernames and sync timestamps, then runs five steps, recording per-step timing. Ingestion errors are recorded as step errors and do **not** abort the run. Feature, predict, and insight errors raise (HTTP 500/422).
3. `features.compute.run_feature_sql_for_student` upserts one `features` row from `feature_engineering_single.sql`.
4. `ml.predict.predict` loads the scaler, clips to [0,1], runs both models, upserts `predictions`, and appends `prediction_history` at most once per hour.
5. `InsightEngine.format_insight` reads features/prediction, applies `insights/rules.py` thresholds on raw values, ranks weaknesses by regressor importance, adds composite patterns and score velocity.

Other routes: `POST /pipeline/batch`, `POST /predict/{id}`, `GET /prediction/{id}`, `GET /insights/{id}`, `GET /ranking`, `GET /features/{id}`, `/students` CRUD-ish (POST, GET, PATCH, `/status`, `/history`), `/ingest/*`, `/admin/retrain`, `/admin/retrain/status`, `/health`, `/health/detailed`. No authentication on anything except `/admin` (header key). Verified.

## 4. Ingestion semantics

- **Synthetic coding**: `STUDENT_PROFILES` covers student IDs 1-8 only. `generate_coding_records` uses unseeded `random` (dates within the last 180 days), so output differs per run. For an ID outside 1-8 without a LeetCode username, `ingest_coding_activity` raises `ValueError` (pipeline records a failed step), while `app/routers/ingest.py` instead generates 30 random rows. Verified.
- **LeetCode** (`leetcode_api.py`): one GraphQL call for `submitStats` totals per difficulty. It then **fabricates** one row per solved problem: 70% dated by cycling the last 30 days, 30% random within 90 days. Real per-problem dates are not available. Row `problem_id`s are synthetic (`<user8>_<difficulty>_r/s####`). The pipeline deletes all existing `coding_activity` for the student before inserting. Data source label: `real_leetcode_stats`.
- **GitHub** (`github_api.py`): up to 10 most recently updated repos; per repo the **total** commit count (Link-header trick) and `commit_date = pushed_at` date. Per-repo count failures fall back to `1` silently. Unauthenticated limit 60/hr; `GITHUB_TOKEN` optional. Rows are inserted with `ON CONFLICT DO NOTHING`, so a repo with new commits on a new `pushed_at` date adds a second row with a cumulative count (likely double counting; unverified).
- **Fallback**: if a real API call fails, the pipeline silently uses synthetic data (only for IDs 1-8 or else nothing) and reports `data_source: "synthetic"` in the step, but the student-facing score is computed regardless.
- **Freshness**: real-API calls are skipped for 24h after `*_last_synced` unless forced; step reports `cached`.
- `validators.py` checks coding/GitHub records in Python before insert (coding path only in pipeline).

## 5. Feature computation

Five features: `total_problems` (count), `avg_difficulty` (easy=1, medium=2, hard=3 mean), `consistency_score` (distinct active ISO weeks in the last 90 days / 13, capped at 1), `commit_frequency` (sum of commits / days since earliest `commit_date`), `cgpa` (from `students`). Two SQL variants must be kept in sync (not compared here). `python -m features.compute` runs the full SQL, loads, fits a `MinMaxScaler` on all rows, saves `models/scaler.pkl`, and writes `features/features_{raw,scaled}.csv`. The scaler is fit on the current population (8 seed students at boot), so a student's scaled values depend on who else is in the DB. Consistency is derived from fabricated LeetCode dates (see §4).

## 6. Model training and inference

- `ml/labels.py`: label = weighted sum of **the same scaled features** (weights cgpa 20, problems 15, difficulty 20, consistency 25, commits 20) + Gaussian noise (σ=5, seed 42), clipped; category thresholds ≥65 Ready, ≥40 Near Ready, else Needs Improvement.
- `ml/train.py`: reads `features/features_scaled.csv`, trains RandomForest regressor and classifier (`n_estimators=100`, 75/25 split, 3-fold CV, dummy baselines), exports `models/{regressor,classifier}.pkl` and `feature_importances.json`.
- The README's "R² ≈ 0.90" claim measures recovery of a synthetic formula, not placement outcomes; with 8 rows the 25% test split is 2 samples (unverified, not run).
- `ml/predict.py` loads models at **import time**, so retraining via `/admin/retrain` swaps files on disk but the running API keeps old in-memory models until restart (unverified; inferred from module-level `joblib.load`).
- `/admin/retrain`: recompute features, overwrite `models/scaler.pkl` in place (before validation), train into `models/staging/`, smoke-test, then move files into `models/`. State is in-process memory, single-lock; no artifact version or rollback record.
- Model `.pkl` files are committed to git despite a `.gitignore` entry (the entry has an inline comment so it may not match; unverified).

## 7. Dashboard

`dashboard/app.py` (793 lines, Streamlit) calls the API only via `dashboard/api_client.py` (`requests`, 60s timeout, `API_URL` env). Covers student list/status, pipeline trigger, prediction/insights/features, ranking, history, student create/update. It exposes data-source labels per pipeline step; the UI copy says blank usernames mean "synthetic". Verified by grep, UI not run.

## 8. Tests

| File | Boundary |
|---|---|
| `test_core.py`, `test_insights.py` | Pure logic and rules (some patch app startup) |
| `test_github_api.py`, `test_leetcode_api.py` | Mocked HTTP |
| `test_api.py`, `test_pipeline.py` | Real Postgres seeded with `seed.sql` and trained models (not run) |

Ran with `venv/Scripts/python.exe -m pytest` on the four mock-based files: **23 passed**. With the system Python, 2 fail on missing `psycopg2`. **Untested**: admin retrain, SQL/feature parity between the two variants, training, migrations on a clean DB, ingest routers, dashboard, cooldown/cache logic, auth (none exists).

## 9. Known limitations

- Labels are constructed, not outcomes; scores are a readiness *proxy* only.
- Fabricated LeetCode timestamps; GitHub dates are `pushed_at`; aggregate counts drive features.
- Silent synthetic fallback and unseeded synthetic generators.
- No auth or per-user data isolation; open student endpoints; admin key unset is only a warning (and an empty `X-Admin-Key` would match an unset `ADMIN_KEY`; unverified).
- `.env` copied into the Docker image (no `.dockerignore`); `docker-compose.yml` hardcodes DB credentials and does not pass `ADMIN_KEY`.
- No migration tooling; schema/migration drift (§2). `sqlalchemy` is in `requirements.txt` but unused by the code reviewed (not grepped exhaustively). `datetime.utcnow()` is used in places.
- No `models/` versioning; unpinned reproducibility of CSV artifacts committed under `features/`.
- Unknown: whether `make up` boots cleanly end to end today; LeetCode GraphQL stability and terms; actual test results for DB-backed tests.

## 10. Open decisions (from PRD §19; none resolved here)

1. Assessment target: real placement outcome vs. preparation assessment until valid outcome data exists.
2. Identity/authentication mechanism and per-user data isolation.
3. GitHub access: public-only vs. delegated authorization.
4. LeetCode source: is the current GraphQL interface permitted/stable, and can it provide per-problem dates?
5. Which academic data (CGPA) is necessary vs. optional.
6. Cloud provider, background jobs, model artifact storage, desktop updater.
7. Handling of the synthetic fallback and demo data: remove, or isolate behind an explicit demo mode.
8. ~~Migration strategy~~ — decided in Phase 3: ordered SQL runner (see report).
