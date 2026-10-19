# Privacy, export/deletion, operator policy

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
- `GET/PUT /me/privacy` — optional research consent (default off). Grant/revoke is audited (`consent.research_granted` / `consent.research_revoked`). Consent is separate from product use: assessments need none. The only research use is the operator export below, which reads this flag at run time.

## Research export (operator only)
- `python -m ml.forecast.export --out <dir> --i-understand-this-exports-research-data` — a CLI, never an API route. Without the flag it exits 2 and writes nothing. Audited as `research_export.created` (export id only).
- Includes only users with `research_consent_at` set when it runs, `provenance='observed'` `github_contribution_day` rows (synthetic and rejected rows excluded), newest collected value per day. Columns: `pseudo_id, day, contributions, value_state`. No email, name, username, profile or user id.
- `pseudo_id` = first 16 hex of SHA-256(per-export random salt + user id). The salt is discarded, so ids differ between exports and cannot be linked or reversed by the file alone.
- A `manifest_<id>.json` beside the CSV holds the data SHA-256, row and user counts, and timestamp.
- **Revoking consent** removes the user from every *future* export. **Past exports are files outside the database**: they carry no link back to the user, so they cannot be found, edited or recalled by us. Account deletion likewise cannot reach them. The consent text says so. Whoever holds an export must delete it per their own retention policy; this repo does not track where exports go (unverified/untracked).

## Retention
- **Primary database:** deleted immediately on request, as above.
- **Replicas:** none in this repo's Compose setup; a managed replica follows primary deletes via replication.
- **Backups:** *not configured or verified in this repository.* Policy to disclose and enforce at the deployment layer: backups are immutable, not edited on user deletion, and expire after the operator-set retention period (target ≤ 35 days); a restore must re-run deletions for `data_requests.kind='deletion'` rows completed after the backup date. The restore re-application step is **not automated** yet.
- **Audit and tombstone rows:** retained indefinitely (no personal values).

## Operator policy
- Operator = `pis_operator` role claim only. `/admin/*`: model list, approve/activate/rollback/retrain (each writes an audit event with the operator's subject), `GET /admin/audit-events`, `GET /admin/sync-failures` (provider, status, safe error code, counts; no user or username fields).
- No admin route lists or reads user profiles/observations. Legacy `students` routes are operator-only demo data.
