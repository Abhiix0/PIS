# Backend Stabilization Report

> **Historical:** written before the current code; see [current-state](../architecture/current-state.md) for what exists today.

## Decision: migration workflow
**Ordered SQL files + a ~60-line runner (`ingest/migrate.py`)**, not Alembic. Reason: the schema is raw SQL, there is no SQLAlchemy model layer (`sqlalchemy` is unused), and a runner adds no dependency. Revisit (Alembic) if Phase 4's domain model needs autogeneration or downgrades. Rules: files apply in filename order; each runs in its own transaction and is recorded in `schema_migrations`; applied files are never edited; failure exits non-zero; an advisory lock serialises concurrent runners. `sql/schema.sql` is gone (it became `000_baseline.sql`) so there is a single path for fresh installs and upgrades.

## Defects addressed (IDs from `docs/history/defect-register.md`)
| ID | Change |
|---|---|
| D-01 | Non-immutable partial index replaced by `idx_coding_student_date`; static test forbids `CURRENT_DATE`/`NOW()` in index predicates |
| D-02 | `uq_github_activity` created by migration `001_add_github_unique.sql` (dedupes first, idempotent) |
| D-04 | `/admin/*`: 503 when `ADMIN_KEY` unset/short, `hmac.compare_digest` otherwise; compose now passes `ADMIN_KEY`; deployed envs fail startup without it |
| D-07 | Strong-student test builds its own fixture instead of assuming seed student 1 is strong |
| D-08 | `.dockerignore` added (`.env`, `venv/`, `.git`) |
| D-09 | Dead `.gitignore` line removed (artifacts remain tracked; not otherwise changed) |
| D-16 | Compose `version:` key removed |

## Other changes
- `config.py`: `APP_ENV`, `validate()` (collects all errors, never echoes secret values, rejects placeholder values in staging/production). `docker-compose.yml` keeps a clearly local-only DB password default, which `validate()` rejects when `APP_ENV` is staging/production.
- Startup fails fast on config errors, unreachable DB, pending migrations, missing models. Pool closed on shutdown (`close_pool`).
- Request IDs: `X-Request-ID` honoured/generated, returned, logged; unhandled-error body carries it. Router 500s no longer echo exception text (logged server-side instead).
- Seed data only via `python -m ingest.migrate --seed`, refused in staging/production and skipped if students already exist.

## Not done / deferred
- D-03 hidden synthetic fallbacks, D-10 in-band pipeline errors, D-14 PATCH semantics: need Phase 4/6 provenance decisions; untouched.
- Blocking external calls in routes (3.4) reviewed only: sync `def` routes run in FastAPI's threadpool; no change made.
- Retrain's `/admin/retrain/status` still returns `str(e)` (admin-only).
