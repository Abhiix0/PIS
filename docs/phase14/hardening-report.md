# Phase 14 — Hardening report (partial)

Environment: no live Postgres or Docker, no Rust/Tauri build, no browser. Only DB-free checks were run.

## Verified (ran)
- `pytest` DB-free set (core, insights, github/leetcode adapters, auth, config, ingestion contracts, route coverage): 192 passed, 2 skipped.
- New `tests/test_route_coverage.py`: every registered route except `/health*` and docs returns 401 anonymously (53 cases); oversized `Content-Length` returns 413.
- Desktop: `npm run typecheck`, `npm run lint`, `npm test` (29) pass; `npm audit --omit=dev`: 0 vulnerabilities.
- `git grep` for token/private-key patterns in tracked files: no hits; no `.env`/key files tracked.
- No CORS middleware exists (desktop is non-browser origin; no cross-origin access granted). Tauri capability is `core:default` + opener URL only (no shell/fs). CSP is restrictive; `connect-src https:` is broad (tracked below).

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
