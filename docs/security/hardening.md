# Hardening report (partial)

Environment: no live Postgres or Docker, no Rust/Tauri build, no browser. Only DB-free checks were run.

## Verified (ran)
- `pytest` DB-free set (core, insights, github/leetcode adapters, auth, config, ingestion contracts, route coverage): 192 passed, 2 skipped.
- New `tests/test_route_coverage.py`: every registered route except `/health*` and docs returns 401 anonymously (53 cases); oversized `Content-Length` returns 413.
- Desktop: `npm run typecheck`, `npm run lint`, `npm test` (29) pass; `npm audit --omit=dev`: 0 vulnerabilities.
- `git grep` for token/private-key patterns in tracked files: no hits; no `.env`/key files tracked.
- CORS (added 2026-10-24, phase 1.1): `CORS_ALLOWED_ORIGINS` allow-list, empty by default; `*` is refused in staging/production. Tauri capability is `core:default` + opener URL only (no shell/fs). CSP is restrictive; `connect-src https:` is broad (tracked below).

- Secret-pattern scan of all tracked files, 2026-10-24 (AWS/GitHub/OpenAI/Slack token shapes, private-key headers, quoted `secret|password|token|api_key` assignments of 8+ characters): no matches. Git history was not scanned.
- Phase 3.1 tests (ran on a scratch Postgres 15): first-login user creation, profile bounds, per-route cross-user 404 for every id-bearing route, evidence determinism, operator routes (`tests/test_admin.py`).

## Accepted pilot limitations
- Rate limiting (`app/auth.py`) is per process: with more than one API task each keeps its own counters. Accepted for the pilot (single task); needs a shared store before scaling out.

## Not verified / open
- Python dependency scan (`pip-audit` not installed), Rust crate scan.
- Owner-isolation, sync recovery, migration/backup restore, model rollback demos: tests exist but need a live DB; not run here.
- Performance p50/p95, desktop cold start, keyboard/contrast/scaling review: not measured.
- Update signing: not configured.
- Body limit trusts Content-Length (chunked uploads uncapped) — see `shortcut:` in `app/main.py`; release blocker only if exposed publicly without a proxy limit.
- Narrow CSP `connect-src https:` to the production API origin before release.
- Logs include request path (student id) but not query strings or tokens.

## Release blockers
Exit gate not met: backup restore, rollback, failed-sync recovery demos and performance baseline are unmeasured.

## Dependency and secret audit (Phase 9.2, 2026-10-24)
- `pip-audit -r requirements.txt` (before): 41 advisories in `fastapi`/`starlette` 0.37.2 (14), PyJWT 2.8.0, requests 2.32.2, python-dotenv 1.0.1, scikit-learn 1.4.2. **Fixed** (direct, low-risk, 349 backend tests pass): PyJWT 2.15.1 (token verification library), requests 2.34.2, python-dotenv 1.2.4; one mypy typing fix in `ingest/github_api.py`. `pip-audit` was installed into the local venv only.
- **Open, owner decision:** `starlette` 0.37.2 (14 advisories; severities not read) is pinned by `fastapi==0.111.0`. Moving to a current FastAPI/Starlette was tried and reverted: newer FastAPI wraps routers in `_IncludedRouter`, which breaks route enumeration in `tests/test_route_coverage.py`, `tests/test_api_v1.py` and the API-surface drift test, so it needs a reviewed refactor, not a version bump. Mitigations in place: the app serves no static files and accepts no form or multipart bodies (JSON only, 64 KiB cap). Treat as a blocker for a public release, not for a small private pilot.
- `scikit-learn` 1.4.2 (PYSEC-2024-110, a text-vectorizer issue; the app uses no text vectorizer). Not upgraded: model bundles are pickled with 1.4.2 and would need retraining.
- `npm audit --omit=dev` (apps/desktop): 0 vulnerabilities. `cargo audit`: not installed, not run.
- Secret scan, tracked files and full git history (106 commits; AWS, GitHub, OpenAI-style keys, private-key headers; no `.env`, `.pfx`, `.pem` or key file ever added): no matches. Regex scan only; `gitleaks` is not installed.
