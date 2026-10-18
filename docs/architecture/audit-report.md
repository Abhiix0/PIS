# Foundation audit — 2026-10-18

Scope: prove the foundation from a clean state. Nothing tagged, no packaging started.
Branch `revamp`, base commit `c7c6ee7`.

## Setup (clean-state equivalent)

Deleted `venv/`, `apps/desktop/node_modules`, `apps/desktop/dist`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.coverage`.
Rebuilt with Python 3.12.13 (project targets 3.11+; 3.11 not installed on this machine) and Node 24.13 / npm 11.6.

DB: the machine's PostgreSQL 18 service on :5432 rejected `pis_user` (password), so a throwaway PostgreSQL 18.4 cluster
was created with `initdb` on port 55432 (roles `postgres` trust, `pis_user` with CREATEDB). CI uses PostgreSQL 15; 18 was used here.

## Results

| # | Check | Command | Result |
|---|---|---|---|
| 1 | Python install | `python -m venv venv && pip install -r requirements-dev.txt` | OK (first attempt hit a transient "no versions" network error; retry OK) |
| 2 | Lint | `ruff check .` | All checks passed |
| 3 | Format | `ruff format --check .` | 82 files already formatted |
| 4 | Types | `mypy` | no issues in 23 source files |
| 5 | Migrations + seed | `python -m ingest.migrate --seed` | applied 10 migrations on an empty DB |
| 6 | `make check` (initial; final re-run: lint clean, **225 passed**, coverage 79.64%) | `make check` | **2 failed, 223 passed**, coverage 79.64% (floor 79%) |
| 7 | pytest, 3 random seeds | `pytest --no-cov -p randomly --randomly-seed={1,2,3} tests` | after fixing 6a and 6b: seeds 1, 2, 3 each **225 passed** |
| 8 | Desktop install | `npm ci` (apps/desktop) | 241 packages |
| 9 | Desktop typecheck / lint / format / test / build | `npm run typecheck`, `lint`, `format`, `test`, `build` | all exit 0; vitest 8 files, 54 tests passed; vite build OK |
| 10 | `make check-ui` | `make check-ui` | passed (54 tests) |
| 11 | Link check | ad-hoc script: every relative link in `git ls-files '*.md'` must resolve | 40 md files, 42 relative links, 0 broken. External URLs not fetched |
| 12 | Secret grep | `git grep -nIE` for AWS keys, GitHub tokens, private-key headers, Slack/`sk-` keys, quoted `secret/token/password/api_key = "…"` | no matches. Tracked env files: only `.env.example`, `apps/desktop/.env.example` |
| 13 | Docker build | `docker build` | **blocked**: Docker daemon not running (`dockerDesktopLinuxEngine` pipe missing) |

## Failures found

- **6a (fixed)**: `tests/test_ingestion_contracts.py::test_every_scaled_feature_is_in_the_data_dictionary` read the removed path
  `docs/data-dictionary/features.md` (stale after the docs consolidation). Pointed at `docs/data/data-dictionary.md`; the test body is unchanged. 18/18 in that file pass.
- **6b (fixed, test only)**: `tests/test_sync.py::test_unexpected_adapter_crash_still_closes_the_run` asserted `pytest.raises(KeyError)`, but the `TestClient` no longer re-raises the background-task error.
  The product is correct (run closed as `failed` / `internal_error`). The test now keeps the adapter-crash setup and asserts the `sync_runs` row (`status='failed'`, `safe_error_code='internal_error'`, `completed_at` set) and a `sync_finished` record with `sync_status='failed'` (caplog). Product code untouched. Cause of the lost propagation not investigated further.
- **Hygiene (fixed)**: `.coverage` was tracked in git. Untracked it and added it to `.gitignore`.

## Not verified

- Docker image build and `make up` / `make test` / `make health` (daemon down).
- Python 3.11 specifically (ran on 3.12.13), PostgreSQL 15 specifically (ran on 18.4).
- Boot chain `features.compute` -> `ml.train` -> `ml.bundle bootstrap` -> `ml.predict` -> `uvicorn` as an end-to-end run (only the pieces the tests exercise).
- Tauri build, signed installers (`apps/desktop/src-tauri`), desktop against a live API.
- AWS/Terraform (`deploy/aws`): never planned or applied; live IdP/JWKS auth.
- Real GitHub/LeetCode provider calls (all HTTP mocked).
- External link reachability; `npm audit` / `pip-audit` dependency vulnerabilities; git history secret scan (only the working tree was grepped).
- CI workflows (`.github/workflows/*`) were read, not executed.

## Exit status

All checks green except #13 (blocked, no Docker daemon).
