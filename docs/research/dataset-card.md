# Dataset card: demo feature set (Phase 7)

| Item | Value |
|---|---|
| Files | `features/features_raw.csv`, `features_scaled.csv`, `features_labeled.csv` (from `sql/seed.sql`) |
| Origin | **Synthetic.** 8 demo students; activity rows have `provenance = synthetic` |
| Unit of analysis | One row per student (a point-in-time aggregate) |
| Timestamps | None kept in the CSVs. `commit_frequency` uses repo `pushed_at`, not commit dates (`docs/data-dictionary/features.md`) |
| Target | `readiness_score` = weighted formula of min-max scaled features + N(0, 5) noise, seed 42. **Not an outcome.** |
| Coverage / missingness | Complete by construction. Real users would have missing data, and the legacy `features` table writes missing as 0 |
| Duplicate / dependence risk | One row per student, so none now. Repeated snapshots per student would need group splits (the runner already groups by `student_id`) |
| Permitted use | Pipeline smoke tests, demos, unit tests. **Forbidden:** any claim about placement, any evaluation of real users |
| Excluded | Real-user `source_observations` (no feature builder yet); all synthetic rows from any future real evaluation |

## Leakage audit
- **Target leakage (inherent):** the label is a deterministic function of the inputs. High scores show formula recovery, not skill. Labels need full-dataset scaling, so the target is fixed before splitting. Model inputs are scaled inside each training fold.
- **Post-outcome fields:** none exist, because there is no outcome.
- **Prediction-time availability:** CGPA is self-reported or manual. Whether it is known at prediction time depends on the use case, which is not defined yet.

## Minimum adequacy before ambitious models
Real, observed, consented data and a defined outcome or forecast target. Sample size comes from a power calculation on the target variance (see `initial-experiment-protocol.md` §2). At n=8 only baselines are run, and the confidence intervals are too wide to rank models.
