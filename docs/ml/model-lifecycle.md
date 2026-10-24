# Versioned inference

**Assessment types** (`assessment_type` on `predictions`/`prediction_history`):
`ml_readiness_proxy` (score + category from the active model; synthetic-formula target, not a placement outcome),
`insufficient_evidence` (no score; `reason` says why: no features, null/non-finite input, CGPA outside 0-10).
(The former rule-based `insights/` engine is no longer in the repo.)

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
removing it is a separate retraining change). Limitations: scaler fit on all rows before the train/test split (see the model-lifecycle limitations).

## Model card: legacy readiness bundle (Phase 8.1, 2026-10-24)
- **What it is:** a RandomForest regressor and classifier (`models/bundles/<version>/`) that re-learn the weighted formula in `ml/labels.py` plus fixed-seed Gaussian noise (sigma 5) from the five legacy features.
- **Trained on:** the 8 synthetic demo students in `sql/seed.sql` (`provenance = synthetic`). Labels are constructed, not observed outcomes.
- **Validation:** none beyond a pipeline smoke test. It is not validated and cannot be: there is no outcome to validate against. `ml/experiment.py` only measures how well models re-learn the formula.
- **Allowed use:** local demo path and operator experiments. **Not** used for real users: `POST /api/v1/assessments` never calls a model and stores `readiness_score = NULL` (checked by `tests/test_quarantine.py`; no `app/` or `services/` module imports `ml.predict`). The desktop labels any legacy score as "Demo formula score" / "Legacy demo score", and real accounts never receive one.
- **Not claimed:** any prediction of hiring or placement. It outputs a readiness proxy of a hand-written formula.
- **Reproducibility check (2026-10-24):** `python -m ml.experiment` was run on a scratch copy of the current `features/features_raw.csv`. The dataset differs from the committed `experiments/baseline-synthetic-a7d069146a57.json` (8 rows, sha256 `811671dbcd64...` versus 9 rows, `a7d069146a57...`), so the committed metrics were **not** reproduced and the mismatch is unexplained beyond the data difference (seed and label-noise settings match). The committed report was not changed.
