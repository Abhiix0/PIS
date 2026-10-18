# Baseline Test and Startup Report

> **Historical:** written before the current code; see [current-state](../architecture/current-state.md) for what exists today.

Date: 2026-10-13. Branch `revamp`, base commit `aa0c99a`. The working tree was clean before the run and no tracked file was modified (only `docs/history/` was added).
Everything below was **executed** unless marked *not run*.

## Environment

| Item | Finding |
|---|---|
| Supported runtime | Python **3.11** (`Dockerfile`: `python:3.11-slim`) with the pins in `requirements.txt` (fastapi 0.111, pandas 2.2.2, scikit-learn 1.4.2, numpy 1.26.4 …). Postgres **15** (`postgres:15-alpine`). |
| Host Python / `venv/` | Python 3.14.2 with **unpinned newer** libraries (pandas 3.0.1, scikit-learn 1.8.0, numpy 2.4.3, fastapi 0.135.2). Good enough for the mock-based tests, not a faithful reproduction of the supported stack. |
| Dashboard image | `dashboard/Dockerfile` installs only `streamlit==1.35.0` and `requests==2.32.2`, independent of `requirements.txt`. |
| Host conflicts | A host Postgres already listens on `:5432`, so the repo's `docker-compose.yml` cannot bind its `db` port as written. Unrelated Supabase containers were running and were left untouched. |
| Isolation used | Separate compose project `pis_p1`, a scratch copy of the compose file (host ports 15432 / 18000 / 18501, own volume), and **copies** of `models/` and `features/` mounted into the API container (the real compose mounts the repo directories and boot overwrites them, see D-09). Scratch files are outside the repo. Only the `pis_p1` volume and containers were removed afterwards. |

## Commands run and results

| # | Command (abridged) | Result |
|---|---|---|
| 1 | `git status --short --branch` | clean, `revamp...origin/revamp` |
| 2 | `venv/Scripts/python.exe -m pytest tests/test_core.py tests/test_insights.py tests/test_github_api.py tests/test_leetcode_api.py -q` | **23 passed** (4.5 s) |
| 3 | `python -m compileall -q app services ingest features ml insights dashboard tests config.py` (venv) | OK, no syntax errors |
| 4 | Lint | **Not available**: no linter config in the repo and `ruff` / `pyflakes` are not installed. |
| 5 | `docker compose -p pis_p1 -f <scratch compose> build` | OK but slow (> 10 min). No `.dockerignore`, so the 706 MB `venv/` and the local `.env` are in the build context (D-08). |
| 6 | `up -d db` with the **repo's unmodified `sql/schema.sql`** on an empty volume | **FAIL.** `ERROR: functions in index predicate must be marked IMMUTABLE` at `schema.sql:63`; container `pis_p1-db-1` **exited with code 3** (D-01). |
| 7 | Same with a scratch copy of `schema.sql` minus the `idx_coding_recent` statement | db healthy. After init: 8 students, 79 coding rows, 23 github rows, 0 features, 0 predictions. `github_activity` has **no** unique constraint beyond the PK (D-02). |
| 8 | `up -d api dashboard` (runs `entrypoint.sh`: `features.compute` → `ml.train` → `ml.predict` → uvicorn) | API up in about 40 s. See "Boot output". |
| 9 | `curl` health and core workflows | See "Workflows observed". |
| 10 | `docker exec pis_p1-api-1 pytest tests/ -v` on a **pristine** first boot | **41 passed, 1 failed, 0 skipped** (3.5 s). Failed: `tests/test_api.py::test_insights_strong_student_has_no_weaknesses` (`assert 3 <= 1`). The same failure occurred on an earlier run against a DB I had already probed. Cause in D-07. No test was edited. |
| 11 | Migrations 001–003 re-applied to the initialised DB | Idempotent (NOTICE "already exists"). `001_add_github_unique.sql` succeeds once, then fails with `relation "uq_github_activity" already exists`. |
| 12 | Pipeline for student 1 after applying `001_add_github_unique.sql` | `github_ingestion` succeeded (18 synthetic rows). Confirms D-02. |
| 13 | Dashboard: `GET :18501/` → 200; `/_stcore/health` → `ok`; inside the dashboard container `GET http://api:8000/health` → `{"status":"ok","version":"1.0.0"}` | Dashboard serves and the container reaches the API. Page interactions were **not** exercised (no browser). |
| 14 | `make up`, `make test`, `make test-local`, `make pipeline-all` against the repo's own compose file | **Not run** (host `:5432` busy; would hit D-01). The `Makefile` calls `docker-compose` (v1 binary is present). |
| 15 | Real LeetCode GraphQL | **Not run** (mocked tests only). |
| 16 | Real GitHub API | Reached incidentally: the pipeline for a student with `github_username=torvalds` got to the DB insert (the error came from the missing constraint), so the unauthenticated fetch returned data. The payload was not inspected. |

## Boot output (first boot on seed data)

- `features.compute`: every one of the 8 seed students has `consistency_score = 0.0` (seed dates are all in 2024; the feature uses the last 90 days). Raw `total_problems` ranges 4–18.
- `ml.train` on 8 rows: labels Needs Improvement 5 / Near Ready 2 / Ready 1; the 25 % test split is **2 rows**; regressor RMSE 4.24 and R² 0.899 on those 2 rows, 3-fold **CV RMSE 20.06 ± 10.98** (dummy 29.24); classifier test accuracy **0.50**, CV 0.61 ± 0.08 (dummy 0.61). sklearn warned that the least populated class has 1 member. `consistency_score` importance is 0.000. Importance drift versus the committed JSON: `cgpa 0.105 → 0.300`.
- `ml.predict`: 8 predictions written; `/health/detailed` reported `status: ok`, `student_count: 8`.

## Workflows observed (disposable stack)

| Call | Result |
|---|---|
| `GET /health`, `/health/detailed` | 200; models present, DB connected |
| `GET /students`, `/students/1`, `/features/1`, `/prediction/1` | 200 |
| `POST /pipeline/1` right after boot | **429** (5-minute cooldown; features were computed at boot) |
| `POST /pipeline/1?force_refresh=true` (clean DB) | **200**, but step `github_ingestion` has `status: error` ("no unique or exclusion constraint matching the ON CONFLICT specification"), and a score is still returned (D-02, D-10) |
| `POST /pipeline/batch` with `[2,3,99]` | 200; unknown id 99 comes back as an in-band error item |
| `POST /predict/2`, `GET /insights/2`, `GET /ranking?limit=3` | 200 |
| `POST /students` (new / duplicate email), `PATCH` with cgpa 11 | 201 / 409 / 422 |
| `PATCH /students/9 {"leetcode_username":""}` | 200, empty string stored (D-14) |
| `POST /ingest/coding/9` | 404 (no synthetic profile) |
| `POST /ingest/coding/real/9` | 200, **30 invented rows**, `source: synthetic`, for a student with no profile or username (D-03) |
| `POST /admin/retrain` with `X-Admin-Key: wrong` | 403 |
| `POST /admin/retrain` with the header omitted | 422 |
| `POST /admin/retrain` with an **empty** `X-Admin-Key` header while `ADMIN_KEY` is unset | **202; the retrain ran and reported `completed`** (D-04) |
| After that retrain: `POST /predict/2` | returned 56.74; a fresh process loading the on-disk models gives **83.72** (D-05) |

## Not verified

- Real LeetCode behaviour; GitHub with a token; rate limits beyond the mocks.
- Streamlit page interactions (only HTTP reachability and container-to-API connectivity).
- The repo's own `docker-compose.yml` on a clean volume past the D-01 failure (all later steps used the scratch-patched schema).
- Whether `.env` actually ended up in the image layer (a local `.env` exists and no `.dockerignore` does; layers were not inspected).
- Concurrency and performance.
