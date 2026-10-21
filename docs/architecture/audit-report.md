# Foundation audit — status 2026-10-21

Scope: what has been verified on this machine, and what has not. Earlier 2026-10-18 figures (225 tests, 54 desktop tests,
79.64% coverage) are superseded and removed; the two failures found then (`test_sync` adapter-crash assertion, stale
data-dictionary path) are fixed and no longer listed.

## Test environment

DB tests need `TEST_ADMIN_DATABASE_URL` (a role that can `CREATE DATABASE`). With it set, `tests/conftest.py` creates a
throwaway database, migrates and seeds it (`migrate(dsn, seed=True)`), computes features, trains one tiny bundle into a tmp
dir, and drops the database at session end. Without it, DB tests run on the ambient `DATABASE_URL` or skip.
Local runs used a throwaway PostgreSQL cluster on port 55432; CI is configured for PostgreSQL 15.

## Results

| Check | Status | Evidence |
|---|---|---|
| Backend pytest, random seeds 1, 2, 3 | **run** (Phase 1b) | 277 passed per seed, 0 skipped |
| Coverage | **run** (Phase 1b) | 82.50% (floor 79%) |
| `ruff check`, `ruff format --check`, `mypy` | **run** (Phase 1b) | clean. Not re-run in Phase 2 (docs only) |
| Desktop `npm test` (vitest) | **run** (Phase 2) | 8 files, 55 tests passed |
| Markdown link check | **run** (Phase 2) | ad-hoc script over `git ls-files '*.md'`: 44 files, 43 relative links, 0 broken; external URLs not fetched |

## Not verified

- Docker image build and `make up` / `make test` / `make health`.
- Python 3.11 specifically (ran on 3.12), PostgreSQL 15 specifically (ran on 18).
- Boot chain `features.compute` -> `ml.train` -> `ml.bundle bootstrap` -> `ml.predict` -> `uvicorn` as one end-to-end run.
- Tauri build, signed installers (`apps/desktop/src-tauri`), desktop against a live API.
- AWS/Terraform (`deploy/aws`): never planned or applied. Live IdP/JWKS auth.
- Remote CI: `.github/workflows/*` were read, never executed.
- Real GitHub/LeetCode provider calls (all HTTP mocked).
- External link reachability; `npm audit` / `pip-audit`; git-history secret scan.
