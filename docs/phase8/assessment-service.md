# Phase 8 — Versioned inference

**Assessment types** (`assessment_type` on `predictions`/`prediction_history`):
`ml_readiness_proxy` (score + category from the active model; synthetic-formula target, not a placement outcome),
`insufficient_evidence` (no score; `reason` says why: no features, null/non-finite input, CGPA outside 0-10).
Rule-based recommendations come from `insights/` (`RULES_VERSION`), each with `basis` (rule and observed value) and `limitation`.

**Bundle** = `models/bundles/<version>/` (regressor, classifier, scaler, feature_importances, `manifest.json` with file
sha256, feature order, schema version, target semantics, git revision). Registry: `model_versions` (migration 006).
Lifecycle: `candidate` (smoke test passed; failed -> `rejected`) -> `approved` (operator, note) -> `active` -> `retired`.
Exactly one `active` (partial unique index); activation re-verifies checksums/schema, then swaps in one transaction.
Rollback reactivates the most recently retired version. Inference and startup load only the active bundle and refuse
checksum or feature-schema mismatches.

**Operate** (operator role): `POST /admin/retrain` registers a candidate only. `GET /admin/models`,
`POST /admin/models/{v}/approve`, `.../activate`, `POST /admin/models/rollback`; CLI: `python -m ml.bundle ...`.
`entrypoint.sh` runs `ml.bundle bootstrap` (activates the newest candidate only when none is active; demo boot).

**Snapshots**: every assessment stores `model_version` and `input_snapshot` (raw inputs, schema version, clipped features).
`predictions` holds the latest; `prediction_history` is append-only (UPDATE blocked by trigger) but still throttled to one
row per student per hour, so intermediate assessments within the hour are not retained.

**Scaling**: the scaler is fitted by `features.compute` on the full table and bundled with the models (RF does not need it;
removing it is a separate retraining change). Limitations: scaler fit on all rows before the train/test split (see Phase 7).
