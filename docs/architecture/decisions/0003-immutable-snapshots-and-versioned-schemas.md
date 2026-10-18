# ADR-0003 — Immutable feature snapshots, assessments, and versioned feature schemas

Status: accepted; realised by migrations 004-007 (file names checked, not re-verified against runtime).

## Context
`features` and `predictions` are single rows overwritten on every run; `prediction_history` keeps only score and category. Nothing records what inputs, feature definition, or model produced a score.

## Decision
- `feature_snapshots` (+ normalised `feature_values`, + `snapshot_inputs`) are insert-only. `assessments` reference one snapshot and one `model_versions` row. Recompute = new rows.
- `feature_schemas.version` is the unit of feature-definition change; model versions are bound to one schema version.
- Rule-only assessments use a `model_versions` row with `kind='rule'` so the reference is never null.
- Feature values are normalised rows (not JSON) so provenance/state stay constrainable (ADR-0002).
- Recommendation text is immutable; user action state lives in a separate mutable table.
- Insert-only is enforced in the service layer and by revoking UPDATE/DELETE from the app role (service layer); account deletion is the only delete path.

## Consequences
- Storage grows per assessment; acceptable for a personal-use scale and bounded by the throttle already applied to history.
- Historical results stay explainable after model changes, and deletion must cascade through snapshots (account deletion work).
