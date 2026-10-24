# Verified baseline, 2026-10-23

Phase 1 / Unit 4. Written from source reading plus one DB-free test run made for this record. Branch `main`, working tree clean at start.

**Missing inputs.** The result reports from Units 1-3 were not supplied, and the plan that defined D-01..D-04 and S-01..S-04 was deleted (CLAUDE.md). Nothing from Units 1-3 is assumed. Anything not run in this unit is **Not run** or carries its last recorded status from `audit-report.md`, labelled as such. The definitions of S-01..S-04 are in §4; §6 holds the 2026-10-24 verification run (Phase 1.1/1.2).

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

## 6. Verification run, 2026-10-24 (roadmap Phase 1.1 and 1.2)

Machine: Windows 11, Docker 29.3.1, cargo 1.99, Node (npm). Compose project `nx_p1` with host ports remapped (db 15433, api 18001) through a throwaway override file; no other project's containers, volumes or the local PostgreSQL on 5432 were touched. Only results observed in this run are listed.

| Check | Result | Evidence |
|---|---|---|
| `docker build -t nexgauge-api:p1 .` (runtime image, `INSTALL_DEV=0`) | **Pass** | Runs as uid 999 `app`; `pip list` has no pytest/ruff. |
| Runtime image, `APP_ENV=staging`, dummy non-placeholder `AUTH_*`, scratch Postgres 15 container, no model | **Pass** | `python -m ingest.migrate` applied 10 migrations; `GET /health/ready` 200 `{"status":"ready"}`; `/health/detailed` `model_version: "none"`; `GET /api/v1/me` 401. |
| `docker compose -p nx_p1 up --build` (local mode, `SEED_DEMO_DATA=true`) boot chain `features.compute` -> `ml.train` -> `ml.bundle bootstrap` -> `ml.predict` -> uvicorn | **Pass** (after two findings below) | `/health` 200; `/health/ready` 200; `/health/detailed` 200 with model `v20261024150954878787-23a430c1-09041c`, `student_count` 8; `/api/v1/me` 401 with the error envelope. |
| pytest inside the api container (Python 3.11.17, Postgres 15.19) | **Pass** | 299 passed, 5 skipped (`tests/test_migrate.py` DB tests need `TEST_ADMIN_DATABASE_URL`). |
| Full pytest on host (Python 3.12, scratch Postgres 15 with `TEST_ADMIN_DATABASE_URL`), Phase 1.1 | **Pass** | 304 passed, coverage 84.92% (floor 79%). |
| `ruff check .`, `ruff format --check .`, `mypy` (Phase 1.1) | **Pass** | 96 files formatted, 26 files typed. |
| `tests/test_sync.py::test_unexpected_adapter_crash_still_closes_the_run` x3 | **Pass** 3/3 | Each run 1 passed. |
| apps/desktop `npm ci`, `npm run build`, `npm test` | **Pass** | Build OK; 8 files, 55 tests passed. |
| `npx tauri build` | **Pass** | `NexGauge_0.1.0_x64-setup.exe`, 2276194 bytes, SHA-256 `e8632115a144584df234bb8adddff66a36a494f0fc7224daae5cfd465a233d98` (local build; not a release artefact). Matches the pattern in `install-guide.md`. A stale `Placement Intelligence_0.1.0_x64-setup.exe` from 2026-10-22 sits in the same ignored folder. |
| Packaged app / `tauri dev` against the local API, Origin header actually sent | **Not run** | Needs a person to launch the GUI; recorded in the manual checklist. |
| Clean-machine install, SmartScreen, upgrade | **Not run** | Owner task. |
| Remote CI, Terraform, live IdP, real GitHub/LeetCode | **Not run** | Not available or not authorized. |

Verdicts for the suspected items of §4:

| ID | Verdict | Basis |
|---|---|---|
| S-01 CORS from webview | **Not run in a webview.** API side mitigated | API now answers allow-listed origins (tests, Phase 1.1). Tauri 2 on Windows is documented to use `http://tauri.localhost`, but the origin was not observed. |
| S-02 Production image without models | **Fixed and verified** | Staging-mode container above starts and reports ready with no bundle. |
| S-03 Live OIDC loop | **Not run** | No IdP configured. |
| S-04 `test_sync` flakiness | **Not reproduced** | 3/3 targeted runs and two full-suite runs (3.11 container, 3.12 host) passed. Absence of a failure is not proof. |

Findings from this run:

| ID | Severity | Finding | Status |
|---|---|---|---|
| N-06 | Low | The first `docker compose up` failed: this machine's `.env` has `SEED_DEMO_DATA=false`, so `features.compute` ran on an empty `students` table and crashed in `MinMaxScaler` ("0 sample(s)"). Compose reads `.env`. | Environmental. Re-run with `SEED_DEMO_DATA=true` in the shell. The crash message is unfriendly; not changed. |
| N-07 | Medium | After Phase 1.1 made the image non-root, `ml.train` failed in compose with `PermissionError: [Errno 1] Operation not permitted: 'models/staging/scaler.pkl'` (chmod by uid 999 on a Windows bind mount). | Fixed: `docker-compose.yml` sets `user: root` for the local api service only. The runtime image still runs as non-root. |

## 7. Acceptance record, roadmap phases 1-9 (final, 2026-10-24)
Pass = run and observed here. Not run = could not be run here; the reason is the blocker. Nothing was pushed, released or deployed.

| Phase | Check | Result | Evidence |
|---|---|---|---|
| 1.1 | Staging-mode startup and readiness without a model; CORS allow-list; non-root image | **Pass** | Container run, 200 on `/health/ready`; tests in `tests/test_ops.py`, `tests/test_config.py` |
| 1.1 | Webview actually sends the allow-listed Origin | **Not run** | Needs a person to launch the packaged app |
| 1.2 | Docker compose boot chain, 3.11 container tests (299 passed, 5 skipped), desktop build/tests, `tauri build` installer | **Pass** | §6 |
| 1.2 | Packaged app against the API; remote CI | **Not run** | Owner / GitHub |
| 2 | Owner decisions recorded; docs reconciled | **Pass** (IdP vendor, region, publisher OPEN) | commit `2b155e7` |
| 3.1 | evidence-v2 contract, isolation/lifecycle/operator tests, secret scan | **Pass** | 316 passed at that commit |
| 3.2 | Live IdP, token refresh, logout, role check, real GitHub sync | **Not run** | Needs the owner's IdP tenant and GitHub token |
| 4 | Deterministic rules-v1 assessment (no score, no composite), migration 009 on empty and previous-head databases | **Pass** | `tests/test_assessment.py`, migration tests |
| 5 | Recommendations and comparison | **Pass** | `tests/test_recommendations.py`, API tests |
| 6.1 | Desktop wired to the server contract; first-run checklist | **Pass** (mock/unit level) | 97 vitest tests; no live run |
| 6.2 | Accessibility, contrast, narrow windows | **Pass** (automated and Playwright layout check) | Phase62 tests; screen-reader and real DPI **Not run** |
| 7.1 | Terraform validate, release dry-run, local restore rehearsal, logging tests | **Pass** (local only) | runbook §12 |
| 7.2 | Free-host comparison | **Done as research** | `docs/ops/free-hosting.md` |
| 7.2 | Deployment, HTTPS readiness, rollback, restore drill on a host | **Not run** | Needs the owner's host accounts; $0 constraint |
| 8.1 | Promotion check, quarantine tests, model card | **Pass**; committed baseline **not reproduced** (data differs) | `docs/ml/model-lifecycle.md` |
| 8.2 | Forecast on consented data | **Not run** | No consented data, no approved consent text |
| 0 | Publisher string, icon | **Not run** | Owner supplies both; old icon and `PIS Project` publisher retained |
| 9.1 | CSP without blanket https:, release workflow, user docs | **Pass**; workflow **Not run** | 97 vitest tests, `tauri build --config` accepted |
| 9.2 | Dependency audit | **Partly**: PyJWT/requests/dotenv fixed; starlette (14 advisories) **open** | `docs/security/hardening.md` |
| 9.2 | Secret scan incl. history | **Pass** (regex only) | hardening.md |
| 9.2 | Pilot kit | **Done** (draft) | `docs/ops/release/pilot-plan.md` |
| 9 | Clean-machine matrix, upgrade test, SmartScreen | **Not run** | Owner |
