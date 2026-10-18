# Domain Model, Identity Boundaries, Provenance

Status: **design document**; later realised in migrations 004-007 (see current-state.md). Target DDL: `draft-schema.sql` (a draft, not a migration; syntax **not yet checked against a live DB**, see §9). Decisions: `docs/architecture/decisions/0001`–`0003`. Assumes Path B (preparation assessment, `docs/ml/target.md`), which still needs human sign-off.

## 1. Concepts and lifecycle

```
users 1─1 profiles ─┬─< source_observations >─ sync_runs >─ integration_connections >─ users
                    │        │ (via snapshot_inputs)
                    ├─< feature_snapshots ─< feature_values        feature_schemas (versioned)
                    └─< assessments ─< assessment_evidence         model_versions ─< model_activations
                          └─< recommendations ─ recommendation_states
users ─< data_requests        audit_events (actor → users, nullable)    data_quality_results → sync_runs/observations
```

| Concept | Owner | Lifecycle | Mutable? |
|---|---|---|---|
| User identity | itself | active → suspended → deletion_pending → deleted | status only |
| Profile | user (`user_id`) | created at onboarding; user edits branch/year/CGPA | yes (user-entered fields); `updated_at` |
| Integration connection | user | connected → error/disconnected; one active per (user, provider) | status/timestamps; secret only by `secret_ref` |
| Sync run | connection | running → succeeded/partial/failed | closes once, then frozen |
| Source observation | profile | written by a sync run (or user entry, or demo seed); never edited | **append-only**; a later sync adds rows |
| Data-quality result | sync run | one per rule check | append-only |
| Feature schema | system | new version per definition change | immutable |
| Feature snapshot (+values, +inputs) | profile | one per assessment run, pinned to `as_of` and a schema version | **immutable** |
| Assessment (+evidence) | profile | references exactly one snapshot and one model version | **immutable** |
| Recommendation | assessment | generated with its assessment | text immutable; action state lives in `recommendation_states` |
| Model version / activation event | system | candidate → approved → retired; activation is an append-only log | status; log immutable |
| Audit event | actor | append-only | immutable |
| Export/deletion request | user | requested → processing → completed/failed | status only |

## 2. Replacing `students` (compat plan)

`students` (int `id`, open endpoints) is a dev entity and is **not** an authorization boundary. Target: `users` (identity) 1─1 `profiles` (owned data). All personal-data tables hang off `profile_id`, and every query is scoped by the authenticated user's profile, never by an id in the URL alone.

Migration approach (details in ADR-0001), expand → backfill → switch → contract, each a numbered migration:
1. **Expand** (Phase 5): add the new tables beside the old ones. Nothing is renamed or dropped.
2. **Backfill**: each `students` row becomes a `profiles` row with `origin='legacy_seed'`, `user_id NULL`, `legacy_student_id = students.id`. `profiles` has `CHECK ((origin='real') = (user_id IS NOT NULL))`, so a legacy/demo profile can never be claimed by or merged into an account at the database level. History (`coding_activity`, `github_activity`, `predictions`, `prediction_history`) is kept for them, labelled by origin.
3. **Switch** (Phase 5/6): new API reads/writes the new tables; the legacy tables become read-only for the dashboard, then are retired with the dashboard.
4. **Contract**: drop legacy tables only after a backup and an explicit decision. Not before Phase 8/9.

Real users start with **no** history: legacy rows are never attributed to them.

## 3. Provenance and missingness (in the data model)

`provenance` enum on every observation and every feature value: `observed` (from the source), `user_entered`, `derived` (computed from verified observations), `inferred` (estimated), `synthetic`.
`value_state` enum: `present`, `not_collected`, `source_failed`, `stale`, `measured_zero`.

Mapping to the Phase 4 list: observed/entered/derived/inferred/synthetic → `provenance`; missing-not-collected, missing-source-failed, stale, genuine zero → `value_state`. Enforced by CHECKs, not UI copy:
- `value_num IS NOT NULL` ⇔ state in (`present`, `measured_zero`, `stale`); `measured_zero` ⇒ value 0. So a NULL can never mean zero, and a zero is never a missing value.
- `synthetic` observations must have no `sync_run_id` (they cannot pose as a sync result).
- `profiles.origin` keeps demo/legacy data out of real accounts (see §2).
- `granularity` is `event` or `aggregate`; an aggregate cannot claim `event_at_precision='exact'`. This encodes the existing rule that LeetCode per-problem dates must not be invented from totals.

Time: `event_at` (when it happened at the source, nullable, with `event_at_precision` in `exact|day|repo_push|unknown`) is separate from `collected_at` (when PIS observed it, always set). `event_at` is never filled from `collected_at`. GitHub's `pushed_at` is recorded as `repo_push`, not as a commit date. Staleness is computed against the snapshot's `as_of`, not stored on the observation.

## 4. Snapshots and immutability

- An assessment points to one `feature_snapshot` and one `model_version`; the snapshot lists its exact input observations in `snapshot_inputs`. Later syncs add observations; they never rewrite an old snapshot or assessment.
- `feature_schemas.version` pins names, units, formulas, window and scaling; snapshots and model versions reference it. A model is only applied to snapshots with its own `feature_schema_version`.
- **Immutable**: observations, snapshots, feature values, assessments, evidence, recommendation text, activation log, audit events. **Recomputable**: a new snapshot/assessment from the same inputs (a new row, never an update). **Mutable**: profile fields, connection status, recommendation action state, request status.
- Immutability is enforced in Phase 5/6 by omitting UPDATE/DELETE paths in the service layer and revoking them from the app role on these tables (not yet implemented).
- Retention/deletion: see §7.

## 5. Authorization matrix (default deny)

Roles: **Owner** (the authenticated user, own rows), **Auth** (any other authenticated user), **Operator** (admin key/role), **Worker** (background job identity), **Anon**. `—` = denied. Every owner rule is enforced by a server-side `profile.user_id = :caller` predicate.

| Resource | Owner | Auth (non-owner) | Operator | Worker | Anon |
|---|---|---|---|---|---|
| users | read/update self; request deletion | — | read status; suspend (audited) | — | create only via sign-up |
| profiles | CRUD own | — | — (no personal read without audited break-glass) | read for jobs | — |
| integration_connections | create/disconnect/read own (no secret) | — | read status only | read incl. `secret_ref`, update sync times | — |
| sync_runs | trigger/read own | — | read counts/error codes | create/update | — |
| source_observations | read own | — | — | insert | — |
| data_quality_results | read own | — | read aggregates | insert | — |
| feature_schemas | read | read | create | read | — |
| feature_snapshots/values | read own | — | — | create | — |
| assessments/evidence | read own; request new | — | — | create | — |
| recommendations / states | read own; update own state | — | — | create | — |
| model_versions | — (only the version label on its own assessments) | — | create/approve | read active | — |
| model_activations | — | — | activate/rollback (audited) | read | — |
| audit_events | read own events | — | read all; no update/delete | insert | — |
| data_requests | create/read own | — | process/update status | process | — |
| demo / legacy_seed profiles | read only in explicit demo mode | same | read | — | — |
| cohort / ranking across users | — (non-goal until PRD §19#13 is decided) | — | — | — | — |

Today (`/students/*`, `/ranking`, `/ingest/*`, `/pipeline/*`) is entirely open; this matrix is the Phase 5 target.

## 6. Data dictionary v1

Types/constraints are in `draft-schema.sql`; this table gives meaning and personal-data class (PD = personal data, S = system).

| Table.field | Meaning | Class |
|---|---|---|
| users.auth_subject | opaque identity-provider subject (provider undecided) | PD |
| users.email | only if the IdP mechanism requires it | PD |
| profiles.display_name, branch, graduation_year, cgpa | user-entered; all optional except `display_name`; CGPA retained only if justified (PRD §19#5) | PD |
| profiles.origin | `real` / `demo` / `legacy_seed` | S |
| profiles.legacy_student_id | link to `students.id` during migration, dropped at contract | S |
| integration_connections.external_username | public handle given by the user | PD |
| integration_connections.secret_ref | pointer to a secret store; never a token | S |
| sync_runs.* | counts, `safe_error_code` (no raw errors), `ingestion_version` | S |
| source_observations.provenance / granularity / event_at / event_at_precision / collected_at / value_state | see §3 | PD |
| source_observations.observation_type | e.g. `github_repo_commit_count`, `leetcode_solved_total` | PD |
| data_quality_results.rule_code / outcome | rule applied and result | S |
| feature_schemas.definition | feature names, units, formula, window, scaling | S |
| feature_snapshots.as_of | end of the observation window; staleness reference | PD |
| feature_snapshots.source_coverage / quality_summary | which sources contributed, and their quality | PD |
| feature_values.state / provenance | per-feature missingness and provenance | PD |
| snapshot_inputs | exact observations behind a snapshot | PD |
| model_versions.* | artifact checksum, schema version, dataset ref, code revision, metrics, approval | S |
| assessments.score / interpretation / quality_warnings | readiness *proxy* score and how to read it | PD |
| assessment_evidence | per-feature contribution | PD |
| recommendations.rule_code / evidence_feature / explanation | rule-based; cites its evidence | PD |
| audit_events.metadata | safe metadata only; never credentials or raw payloads | S |
| data_requests.kind / status | export or deletion workflow | PD |

## 7. Retention and deletion (proposed, needs sign-off)

- Account deletion: `users.status → deletion_pending`; a job deletes profile-owned rows (observations, snapshots, assessments, recommendations, connections incl. secrets) and revokes tokens; `users` keeps a tombstone (`deleted`) to preserve audit-event integrity; audit events keep only IDs and event types.
- Disconnect: stops syncing and deletes the secret; whether past observations are kept is a user choice at disconnect (default keep, deletable).
- Raw API payloads are not stored; only normalised values (PRD §10.4).
- Backups: deleted data persists in backups until they roll off. The retention window is **undecided** (depends on cloud provider, PRD §19#6); the privacy summary must state it. Restores must replay deletion requests.
- Synthetic/demo rows are never exported as a user's data.

## 8. Mapping from the current schema

| Today | Target |
|---|---|
| `students` | `profiles` (`legacy_seed`) now; real onboarding creates `users` + `profiles` |
| `students.github_username`, `leetcode_username`, `*_last_synced` | `integration_connections` (`external_username`, `last_success_at`) |
| `coding_activity` | `source_observations` (`leetcode_*`). Existing rows have invented dates, so they are backfilled with `granularity='event'`, `event_at_precision='unknown'`, `event_at=NULL`, provenance `synthetic` for seed rows. For API-sourced legacy rows with fabricated dates, `inferred`, and their invented date is not carried forward. |
| `github_activity` | `source_observations` (`github_repo_commit_count`, `event_at_precision='repo_push'`) |
| `features` (one overwritten row) | `feature_snapshots` + `feature_values` (history kept) |
| `predictions`, `prediction_history` | `assessments` (+ `model_versions` row for the current RF and the formula as `kind='ml'`/`'rule'`, labelled heuristic) |
| `/admin/retrain` in-memory state | `model_versions`, `model_activations` |
| none | `users`, `feature_schemas`, `data_quality_results`, `recommendations`, `audit_events`, `data_requests` |

## 9. Verification and gaps

- **Not verified**: `draft-schema.sql` has not been run. The local Postgres on :5432 rejected the `.env` credentials and Docker was not running. Check with: create a scratch DB, then `psql -v ON_ERROR_STOP=1 -f docs/architecture/draft-schema.sql`. Do this before Phase 5 turns it into migrations.
- Row-level security vs. application-layer scoping is not decided (ADR-0001 leaves it to Phase 5).
- The identity mechanism is open (PRD §19#2); the model only assumes an opaque `auth_subject`.
- Whether `cgpa` is stored at all (§19#5) and the backup retention window (§7) are open.
