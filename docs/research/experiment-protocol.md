# Experiment protocol (Phase 7 runner)

Command: `python -m ml.experiment` (writes `experiments/baseline-synthetic-<data-hash>.json`).

**Status of the research question.** The ML task is unselected. RQ1 in `initial-experiment-protocol.md` (forecast next-4-week GitHub activity) is still unapproved. It needs a commit-level collector that does not exist, because `source_observations` hold only repo `pushed_at` aggregates. The runner is task-agnostic infrastructure, run here on the synthetic demo set as a pipeline smoke test. Any ML in the product is a demo *readiness proxy score*, not outcome prediction. This is "non-outcome preparation intelligence" under the Phase 7 exit gate.

**Recorded per run:** data sha256, feature schema version, target definition, label noise/seed, git revision (+dirty), Python/sklearn/pandas/numpy versions, seed, split protocol, model params, MAE/RMSE, bootstrap 95% CI over students, and a report checksum.

**Split.** `GroupKFold` by `student_id` (leave-one-student-out at n=8). Scaler, and any future selection/tuning/calibration, live inside the per-fold `Pipeline`. No untouched final test set exists at this n. The report says so. Do not tune against this evaluation.

**Baselines.** `mean` (naive), `rule_formula` (transparent weights, no learning), `ridge` (linear), `random_forest` (the shipped family). Primary metric: MAE, with skill vs `mean`.

**Reopen conditions.** Approve a task, collect real consented data, set the minimum sample from a power calculation, hold out a final test set (temporal if forecasting), and add the REFORMS checklist.
