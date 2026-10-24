# Verified baseline, 2026-10-23

Phase 1 / Unit 4. Written from source reading plus one DB-free test run made for this record. Branch `main`, working tree clean at start.

**Missing inputs.** The result reports from Units 1-3 were not supplied, and the plan that defined D-01..D-04 and S-01..S-04 was deleted (CLAUDE.md). Nothing from Units 1-3 is assumed. Anything not run in this unit is **Not run** or carries its last recorded status from `audit-report.md`, labelled as such.

## 1. Environment and commands

| Command | Status | Evidence |
|---|---|---|
| `venv/Scripts/python.exe -m pytest tests/test_core.py tests/test_github_api.py tests/test_leetcode_api.py tests/test_config.py tests/test_route_coverage.py tests/test_forecast.py tests/test_as_of.py -q` | **Pass** (ran, this unit) | 132 passed, 7 warnings (a scipy `L-BFGS-B` deprecation in forecast tests). Python version of `venv` not recorded. |
| Full backend pytest with coverage (`--cov=app --cov=services --cov=ml --cov=ingest`) | Not run (Unit 2.1). No usable DB: `.env` `DATABASE_URL` points at localhost:5433 (connection refused); a server listens on 5432 (psql 18.4 client) but rejected the `.env` credentials, and no `TEST_ADMIN_DATABASE_URL` is set. Last recorded: 277 passed, 82.50% coverage (Phase 1b, `audit-report.md`) | Needs `DATABASE_URL` + `TEST_ADMIN_DATABASE_URL` (CREATEDB role). Floor 79% not checked. |
| `ruff check .` | **Pass** (ran, Unit 2.1, Python 3.12.13 `venv`) | `All checks passed!` |
| `ruff format --check .` | **Pass** (ran, Unit 2.1) | `94 files already formatted` |
| `mypy` | **Pass** (ran, Unit 2.1) | `Success: no issues found in 26 source files` |
| DB-free pytest subset (same 7 files as row 1) | **Pass** (ran, Unit 2.1, Python 3.12.13) | 132 passed, 7 warnings |
| PostgreSQL server version | Not recorded | No server reachable with available credentials. |
| `make check` | Not run | Needs DB and `TEST_ADMIN_DATABASE_URL`. |
| Desktop `npm test` | Not run (this unit). Last recorded: 55 tests (Phase 2) | Not re-run. |
| `make up`, `make test`, `make health`, Docker image build | Not run | Docker not exercised. Never verified per `audit-report.md`. |
| Boot chain `features.compute` -> `ml.train` -> `ml.bundle bootstrap` -> `ml.predict` -> uvicorn | Not run | Needs a migrated, seeded DB. Never verified end to end. |
| Tauri build, installers, desktop against live API | Not run | Never verified. |
| Terraform plan/apply (`deploy/aws`) | Not run | Never verified. |
| Remote CI (`.github/workflows/*`) | Not run | Read only. |
| Real GitHub / LeetCode provider calls | Not run | All HTTP mocked in tests. |
| Live IdP / JWKS auth | Not run | Never verified. |

## 2. Data and ML trace

### 2a. Demo / legacy path (`students`-keyed tables)

| Step | File | Reads -> writes | Status |
|---|---|---|---|
| Seed | `sql/seed.sql` (via `python -m ingest.migrate --seed`; gated by `seed_allowed()` / `SEED_DEMO_DATA`) | -> `students`, `coding_activity`, `github_activity` (8 students, `provenance = synthetic`) | Read; exercised by DB tests (last recorded run, not re-run) |
| Feature SQL | `sql/feature_engineering.sql`, `features.compute.run_feature_sql` | activity tables -> `features` (5 features) | Read; Not run here |
| Scale | `features/compute.py` (`SCALE_COLS`, `MinMaxScaler` fit on all rows) | `features` + `students.cgpa` -> `models/scaler.pkl`, `features/features_raw.csv`, `features/features_scaled.csv` | Read; Not run here |
| Labels | `ml/labels.py` | scaled features -> `readiness_score` = weighted sum (cgpa 20, total_problems 15, avg_difficulty 20, consistency_score 25, commit_frequency 20) + Gaussian noise (seed 42, sigma 5), clipped 0-100; category thresholds 65 / 40. `LABEL_ORIGIN = "synthetic_formula"` | Read |
| Train | `ml/train.py` | labels -> RandomForest regressor and classifier in `models/staging`; `create_candidate` freezes a bundle | Read; Not run here |
| Registry | `ml/bundle.py` | `models/bundles/<version>/` with sha256 manifest, `model_versions` row. Lifecycle candidate -> approved (needs passing smoke test) -> active (checksums re-verified) -> retired; `rollback`. `bootstrap` activates the newest candidate as `local-bootstrap` only when none is active | Read; bundle tests exist (`tests/test_bundle.py`), not in the subset run here |
| Predict | `ml/predict.py` | `students` + `features` -> `predictions` (upsert) and `prediction_history` (at most one row per student per hour; immutable by trigger, migration 006) | Read; Not run here |

Output type is `ml_readiness_proxy` or `insufficient_evidence` (missing / non-finite inputs, cgpa outside 0-10). The model learns the constructed label formula from the seed students, not placement outcomes. Inputs outside the scaler's range are clipped and recorded in the snapshot.

Who calls what: the API (`app/main.py`, `routers/admin.py`) uses `ml.bundle` only (`load_active`, `active_version`, candidate creation, approval, activation). **No `app/` route imports `ml.predict`.** `ml.predict` runs from `entrypoint.sh` at local boot. Stale `.pyc` files for removed modules (`app/routers/predictions`, `services/pipeline`) remain in `__pycache__`; they are not tracked sources.

### 2b. Real-user path

| Step | File | Result |
|---|---|---|
| Connect | `PUT /api/v1/integrations/{provider}` -> `services/sync.py::connect` | Stores a public username, owner-scoped. LeetCode refused unless `LEETCODE_INTEGRATION_ENABLED`. |
| Sync | `POST .../sync` -> `start_sync` -> `execute_run` (background) | `sync_runs` row first, then adapter. Empty result -> `failed`; `ProviderError` -> `failed`, nothing written; all rows rejected -> `failed`; some rejected or partial -> `partial`. |
| Adapters | `ingest/github_api.py`, `ingest/leetcode_api.py`, `ingest/validators.py` | Typed `Observation`s; `validate_observation` before storage. GitHub `event_at` is repo `pushed_at` (precision `repo_push`). LeetCode is aggregate-only. Daily GitHub calendar only when `GITHUB_CALENDAR_ENABLED=true`. |
| Store | `services/sync.py::_store` | Append to `source_observations` with provenance, granularity, precision, `sync_run_id`. |
| Assess | `POST /api/v1/assessments` (`app/routers/v1.py::create_assessment`) | `_build_evidence` summarises the latest run per provider (sums, repo counts, and a rule-based active-weeks trend from calendar days). The insert hard-codes `assessment_type = 'insufficient_evidence'`, no score, no model call. |

**Where real data stops short of the model:** real data ends at `assessments.evidence` (JSON snapshot). `source_observations` never feeds `features`, `predictions`, `prediction_history` or any bundle. `profiles` is not joined to `students`. `create_assessment` imports no model code. So a real user can never receive a score today, by construction.

### 2c. `ml/forecast/`

| Item | Finding |
|---|---|
| What | Research pipeline for RQ1: forecast next-4-week active weeks from 12 weekly GitHub contribution sums. `export.py` writes a daily CSV from `source_observations` for users with `research_consent_at` set and `provenance = 'observed'`. `run.py` builds origins, splits, fits baselines (persistence, user mean, seasonal-naive, Poisson regression), writes `experiments/forecast-<hash12>.json`; `--open-test` opens the final test once (lock file). Tree model and ordinal regression are not implemented. |
| API use | None. `grep` finds no `forecast` reference in `app/` or `services/`. It is CLI only. |
| Report | `docs/ml/forecast-report.md` states: pipeline built and tested, **not run on real data, no forecasting result exists**. Result rows are empty by design. No metric is quoted here because none exists in the report. |
| Tests | `tests/test_forecast.py` and `tests/test_research_export.py` exist. `test_forecast.py` was in the 132-test subset above and passed; `test_research_export.py` was not run. |
| Placeholders | Minimum users per partition, bulk-import and bot thresholds are stated in the report as unvalidated. |

## 3. Workflow map

"Verified" means a test in the last recorded runs covers it, or this unit ran it; no workflow below has been run against a live IdP, a real provider, or a built desktop app.

| Workflow | Files | Status |
|---|---|---|
| Sign-in | `apps/desktop/src/auth/{oidc,native,session}.ts(x)`, `app/auth.py`, `GET /api/v1/me` | Server JWT verification: tested with mocks (`tests/test_auth.py`, last recorded run). Desktop session: unit tests only (`session.test.tsx`). **Unverified** against a live IdP; Tauri native path never built. |
| Connect integration | `screens/Integrations.tsx`, `routers/v1.py::connect`, `services/sync.py::connect` | Backend tested (`test_sync.py`, last recorded run). UI: unit tests only. **Unverified** live. |
| Sync | `services/sync.py`, `ingest/github_api.py`, `ingest/leetcode_api.py` | Adapter parsing tested with mocked HTTP (`test_github_api.py`, `test_leetcode_api.py` ran in the subset above: pass). Real provider calls **Not run**. |
| View dashboard / assessment | `screens/{Dashboard,Assessment,History,Overview,Plan}.tsx`, `POST/GET /api/v1/assessments*` | Backend tested (last recorded run). Result is always `insufficient_evidence` for real users. Screens: unit tests only; Overview/Plan have no dedicated test file by name. Not run against a live API. |
| Export | `routers/v1.py::export_my_data`, `services/privacy.py::export_data`, `screens/Privacy.tsx` | Backend tested (last recorded run). UI: unit tests only. |
| Delete data | `disconnect(delete_data=true)`, `delete_source_data`, `POST /me/data-requests/deletion` (`confirm=true`), `screens/Privacy.tsx` | Backend tested (last recorded run). Deletion is irreversible and locks the account. Not run live. |

## 4. Defect register

D-01..D-04 are defined in `docs/history/defect-register.md` and `docs/history/backend-stabilization.md`. S-01..S-04 could not be found in any file; the plan that held them was deleted. S-01..S-04 definitions were supplied with the Unit 2.1 task and are recorded below.

Units 1-3 evidence is absent, so "status" below is what the repo records, not a fresh reproduction.

| ID | Severity | Evidence / command | Impact | Reproduction | Priority | Status |
|---|---|---|---|---|---|---|
| D-01 | Blocker (was) | `docs/history/backend-stabilization.md`: non-immutable partial index replaced by `idx_coding_student_date`; static test forbids `CURRENT_DATE`/`NOW()` in index predicates | Fresh DB could not start | Original: empty volume, db exit code 3. Current: migrations are the only schema path (`000_baseline`). Not re-run here | Low (recorded fixed) | Fixed per history; **not re-verified** in this unit (Docker Not run) |
| D-02 | High (was) | `001_add_github_unique.sql` creates `uq_github_activity` | GitHub ingest failed on fresh DB | Not re-run here | Low | Fixed per history; **not re-verified** |
| D-03 | High (was) | History: hidden synthetic fallbacks, ingest routes and pipeline removed. Current code: `sync.execute_run` raises/records `failed` on `ProviderError` and writes nothing; `grep` finds no pipeline/ingest router in `app/` | Scoring on fabricated activity | Code reading only | Low | Fixed per history and code reading; **not re-verified by run** |
| D-04 | High (was) | History: `/admin/*` 503 when `ADMIN_KEY` unset. Current doc says `/admin/*` requires role claim `pis_operator` (`app/auth.py`, `require_operator`) | Admin bypass | Not re-run. The mechanism described in the history (`ADMIN_KEY`) differs from the current one (JWT role); the register does not say which test covers the new path | Medium: confirm coverage | Suspected stale; **not verified** |
| S-01 | – | Packaged desktop fetches a different origin (`http://localhost:8000`); the API has no CORS middleware | Packaged app may fail all API calls | Not run | – | Suspected, not run |
| S-02 | – | Production image has no models (gitignored and in `.dockerignore`); `APP_ENV=staging` may refuse to start for lack of an active bundle | Staging/production boot failure | Not run | – | Suspected, not run |
| S-03 | – | OIDC sign-in loop untested outside mocks | Sign-in may loop against a real IdP | Not run | – | Suspected, not run |
| S-04 | – | Possible order/timing dependence in `tests/test_sync.py`. An independent run did not reproduce it: 294 passed with fixed and random order on Python 3.12 / PG 16 (not run by this unit) | Flaky tests | Not run | – | Suspected, not run |

New observations from this unit (all read, none reproduced by run):

| ID | Severity | Evidence | Impact | Priority | Status |
|---|---|---|---|---|---|
| N-01 | Low | `current-state.md` header says branch `revamp`; `git branch --show-current` returns `main` | Doc drift. File not edited per task rules | Low | Confirmed |
| N-02 | Low | `current-state.md` §6 notes `model-lifecycle.md` names `insights/` (stale) and that `sqlalchemy` in `requirements.txt` is unused | Doc/dependency drift | Low | Confirmed by the doc itself; not re-checked |
| N-03 | Low | Untracked stale `.pyc` for removed modules in `app/routers/__pycache__`, `services/__pycache__` | Noise only | Low | Confirmed (listing) |
| N-04 | Medium | `create_assessment` inserts `insufficient_evidence` unconditionally; `reason` text depends only on whether any provider data exists | Not a defect in the current design; recorded because any later real-user score needs a new feature path (see §5) | Info | Confirmed |
| N-05 | Medium | `apps/desktop/src/lib/assessment.ts` and `screens/Overview.tsx` read `leetcode_solved_all`; no backend code emits it (only `leetcode_solved_easy/_medium/_hard`); only `api/mock.ts` supplies it | Client shows/derives nothing from LeetCode totals on real data (e.g. the `solve` priority never fires) | Medium | Confirmed |

## 5. Architectural limitations and open decisions

Limitations (all from code or `current-state.md` §10):

- Scores exist only for the 8 seeded demo students, from a constructed label formula. No placement-outcome labels exist. Output is a readiness proxy, not a hiring prediction.
- Real users get no score. There is no bridge from `source_observations` / `profiles` to `features` / the model.
- The legacy `students` tables, scaler fit on all rows, and feature SQL are demo-scale.
- GitHub timestamps are `pushed_at`; LeetCode is aggregate-only with no solve dates.
- Rate limiting is per process, not shared across replicas.
- Forecasting has no results; it has never run on real data.
- Stack boot, Docker build, AWS deployment, installers, live IdP, and real provider calls are unverified.

Open decisions (from PRD §19, `docs/product/PIS_PRD.md`; no answers given here):

- Assessment target: placement outcome vs. preparation.
- GitHub access scope.
- LeetCode source and terms.
- Which academic data is required.
- Research consent.
- Release channel.

Additional questions raised by this record, unanswered:

- Whether D-04 coverage of the operator-role path is sufficient. The history describes `ADMIN_KEY`; the code now uses a JWT role.
