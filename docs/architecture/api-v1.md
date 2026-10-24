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
`POST /assessments` snapshots the caller's evidence (`evidence-v2`: CGPA as `user_entered`, the latest run's observations per provider with `sync_run_id`, the weakest provenance among the rows, per-value `value_states`, a `derived` list, and each connection's last sync run) and stores the deterministic **rules-v1** result in `result` (migration 009). Older `evidence-v1` snapshots stay readable and have `result: null`.

`result` = `{assessment_version: "rules-v1", evidence_version, generated_at, stale_after_days, dimensions[], limitations}`. Each dimension (D1 activity consistency, D2 project footprint, D3 LeetCode volume only when `LEETCODE_INTEGRATION_ENABLED`, D4 CGPA context) has `evidence_state` (`no_evidence | stale | partial | sufficient | source_failed`), `values[]` (name, value, provenance, value_state, event_at_precision, collected_at, synced_at, sync_run_id), `rule {id, text}`, `coverage`, `caveats[]`, and `last_sync` after a failed/partial run. The staleness window (7 days) is proposed and unvalidated. A failed latest sync gives `source_failed` while the last-known-good values stay listed.

`assessment_type` is `rules_assessment` when any provider dimension has values, otherwise `insufficient_evidence`. There is **no score and no composite**: `readiness_score` is null for real accounts. Implemented as rules-v1, not validated. Logic: `services/assessment.py`.

`result.recommendations[]` (Phase 5, `services/recommendations.py`): fixed-priority rules, each with `id`, `rule_id` (`r1.connect` ... `r8.no_practice`), `priority`, `dimension`, `action`, `reason`, `evidence_refs[]` (dimension, value name, `sync_run_id`) and a `limitation` line. CGPA never triggers one. Thresholds are named constants, proposed and unvalidated; no claim is made that acting on a recommendation changes any outcome.

`GET /assessments/{id}/compare/{other_id}`: both snapshots must belong to the caller (404 otherwise); `{id}` is the earlier. Returns per-dimension state and value deltas. Values are differenced only when `assessment_version` and `evidence_version` match; otherwise `comparable` is false, `delta` is null and `disclosures[]` says why. State changes and dimensions present in only one snapshot are disclosed. Snapshots without a `result` (older rows) are not comparable.

## Not built (no client needs them yet)
Progress state beyond snapshot comparison, settings.

## Compatibility
Root routes (`/students`, `/pipeline`, `/integrations`, `/profiles`, `/admin`, …) are unchanged and remain for Streamlit and operators. Streamlit uses only root routes and needs no change. Root integration sync is still synchronous (200 with the finished run); v1's is 202.
