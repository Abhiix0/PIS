# API v1 (`/api/v1`)

Live contract: `/openapi.json` (`/docs`). `tests/test_api_v1.py` fails if a v1 route is added without an auth test.
All routes need a bearer token; every query is scoped by the token's `user_id` in the SQL (another user's id = 404).

| Route | Purpose |
|---|---|
| `GET /me`, `PUT /me/profile` | caller + profile (`profile: null` until created); PUT is create-or-replace, 201 then 200 |
| `GET /integrations`, `PUT /integrations/{github\|leetcode}` | connections; public username only |
| `DELETE /integrations/{github\|leetcode}?delete_data=` | 204; stops syncing; `delete_data=true` also erases imported observations; 404 if not connected |
| `POST /integrations/{provider}/sync` | **202** + `{id, status:"running"}` + `Location`; poll `GET /sync-runs/{id}` |
| `GET /sync-runs?provider=&limit=`, `GET /sync-runs/{id}` | run status, counts, `safe_error_code` |
| `GET /me/data-quality` | per connection: last run + quarantined records by rule code |
| `POST /assessments`, `GET /assessments?limit=&offset=`, `GET /assessments/{id}`, `GET /assessments/{id}/evidence` | immutable evidence snapshots, newest first (limit ≤ 100) |
| `GET /me/export`, `POST /me/data-requests/deletion?confirm=true`, `GET /me/data-requests`, `GET/PUT /me/privacy` | export JSON, immediate account erase + lock, request history, research consent. See `docs/data/privacy-and-retention.md` |

Liveness/readiness stay at `/health` and `/health/detailed` (unauthenticated, unversioned).

## Conventions
- **Errors:** `{"error": {"code", "message", "request_id"}}` for every `/api/v1` response (400-class, 413, 422, 429 + `Retry-After`, 500). Validation messages carry `loc` + `msg` only (no echoed input). Legacy routes keep `{"detail": ...}`.
- **Time:** ISO 8601 with `+00:00` (DB pool pins `timezone=UTC`). Nullable fields are always present as `null`.
- **Limits:** body ≤ 64 KiB (Content-Length check only), page size ≤ 100, sync/assessment creation rate-limited (10/min/caller, per process).
- **Long-running work:** sync runs as a FastAPI `BackgroundTask` after the `sync_runs` row is committed. No worker/queue: duration is one provider call set (bounded retries), and a process crash leaves a `running` row that is marked `failed/abandoned` after 15 min. Add a worker if syncs must survive restarts or exceed minutes.
- **Idempotency:** `PUT` resources are idempotent. Sync: in-flight run → 409, inside cooldown → 429, so a retried POST never starts a second run. `POST /assessments` is not idempotent (each call is a new snapshot). Data requests return the open request.

## Assessments for real accounts
Always `assessment_type = insufficient_evidence`, no score. The model's features need per-problem solve history and a daily commit rate that provider data cannot supply without inventing values (see `docs/data/data-dictionary.md`). The snapshot (`evidence-v1`) holds CGPA (`user_entered`) and the latest run's observations per provider (`observed`, with `sync_run_id`). A real-user ML score needs a decision on a validated feature set first (open).

## Not built (no client needs them yet)
Recommendations and progress state, assessment comparison, settings.

## Compatibility
Root routes (`/students`, `/pipeline`, `/integrations`, `/profiles`, `/admin`, …) are unchanged and remain for Streamlit and operators. Streamlit uses only root routes and needs no change. Root integration sync is still synchronous (200 with the finished run); v1's is 202.
