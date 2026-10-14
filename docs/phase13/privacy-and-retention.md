# Phase 13 — Privacy, export/deletion, operator policy

## Data stored (and why)
| Data | Why | Removed by |
|---|---|---|
| `users` (IdP subject, email) | identity, session revocation | email erased on deletion; subject row kept as a locked tombstone |
| `profiles` | assessment inputs | account deletion |
| `integration_connections`, `sync_runs` | sync state (public username only; **no provider token is stored**, so nothing needs revoking) | account deletion (disconnect only marks `disconnected`) |
| `source_observations`, `data_quality_results` | assessment evidence | disconnect with `delete_data=true`, or account deletion |
| `assessments` (immutable snapshots) | history | account deletion only |
| `data_requests` | export/deletion status | kept (ids, kind, status, times) |
| `audit_events` | accountability | kept, append-only; ids/action names only, never tokens or personal values |

## User controls (`/api/v1`)
- `DELETE /integrations/{provider}?delete_data=true|false` — stop syncing; optionally erase imported data. Assessments already created keep their snapshot (immutable); history is unchanged. Sync-run metadata (counts, error codes) is retained.
- `GET /me/export` — JSON `pis-export-v1`: account, profile, integrations, sync runs, observations, assessments (with evidence), requests. Synchronous; no secrets exist to include.
- `POST /me/data-requests/deletion?confirm=true` — immediate, irreversible erase (completed in the response, not queued). Locks the account (`status=deleted`, `sessions_valid_after=now`): the same or any other token for that subject gets 403.
- `GET/PUT /me/privacy` — optional research consent (default off). **Recorded only: no training or research use of real-user data exists**; if one is added it must check this flag.

## Retention
- **Primary database:** deleted immediately on request, as above.
- **Replicas:** none in this repo's Compose setup; a managed replica follows primary deletes via replication.
- **Backups:** *not configured or verified in this repository.* Policy to disclose and enforce at the deployment layer: backups are immutable, not edited on user deletion, and expire after the operator-set retention period (target ≤ 35 days); a restore must re-run deletions for `data_requests.kind='deletion'` rows completed after the backup date. The restore re-application step is **not automated** yet.
- **Audit and tombstone rows:** retained indefinitely (no personal values).

## Operator policy
- Operator = `pis_operator` role claim only. `/admin/*`: model list, approve/activate/rollback/retrain (each writes an audit event with the operator's subject), `GET /admin/audit-events`, `GET /admin/sync-failures` (provider, status, safe error code, counts; no user or username fields).
- No admin route lists or reads user profiles/observations. Legacy `students` routes are operator-only demo data.
