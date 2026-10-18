# ADR-0002 — Provenance and missingness as typed columns with CHECK constraints

Status: accepted; realised by migrations 004-007 (file names checked, not re-verified against runtime).

## Context
Today a missing value is `0` or absent, synthetic fallbacks look like real data, and invented dates are stored as real ones. Phase 2 requires distinguishing observed/entered/derived/inferred/synthetic and missing-not-collected/source-failed/stale/zero.

## Options
1. UI-only labels. Rejected: data can be misread by every other consumer.
2. A JSON blob of metadata per value. Rejected: not constrainable or queryable (PRD §10.5).
3. **Two enums, `provenance` and `value_state`, as columns on observations and feature values, with CHECKs** (chosen), and a separate `event_at` / `collected_at`.

## Decision
- `provenance`: observed, user_entered, derived, inferred, synthetic. `value_state`: present, not_collected, source_failed, stale, measured_zero.
- CHECKs: value is NULL exactly when the state carries no value; `measured_zero` ⇒ 0; synthetic ⇒ no sync run; aggregate ⇒ never `exact` event time.
- `event_at` is nullable with a precision tag and is never backfilled from `collected_at`.
- Staleness is computed against a snapshot's `as_of` and stored on the feature value when it applies.

## Consequences
- Adding a provenance class or state is a migration (enum change); accepted, as these should change rarely.
- Ingestion (Phase 6) must classify every datum on write; "unknown" is not an allowed provenance.
- Feature computation (Phase 6/7) must propagate state; combining a `source_failed` input yields a non-`present` output.
