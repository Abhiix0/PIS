# ADR-0001 — Migrate `students` to `users` + `profiles` by expand/backfill/switch/contract

Status: proposed (Phase 4). Not implemented.

## Context
`students.id` (serial int) is exposed in open URLs and used as the only key. Real accounts need an owner boundary. Existing rows are seed/demo and include fabricated dates.

## Options
1. Rename `students` to `profiles` and add `user_id`. Loses the demo/real separation and pushes seed rows into the real account model.
2. Drop and recreate. Loses history and the dashboard's data; no rollback.
3. **Expand → backfill as `legacy_seed` → switch → contract** (chosen).

## Decision
Add new tables beside the old; backfill each student as a `profiles` row with `origin='legacy_seed'`, `user_id NULL`; a CHECK makes `real ⇔ user_id NOT NULL`. New API writes only new tables. Drop legacy tables in a later, separately approved migration after a backup. Each step is a numbered migration under the Phase 3 runner (Alembic stays rejected; revisit only if downgrade/autogenerate becomes needed).

## Consequences
- No history lost; legacy data can never be attributed to a real user.
- Two schemas coexist for a while; the dashboard keeps working on the legacy tables until it is retired.
- Ownership scoping (app-layer predicate vs. Postgres RLS) is left to Phase 5.
