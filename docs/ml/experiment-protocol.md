# Experiment protocol

## A. Implemented runner

Command: `python -m ml.experiment` (writes `experiments/baseline-synthetic-<data-hash>.json`).

**Status of the research question.** The ML task is unselected. RQ1 in section B below (forecast next-4-week GitHub activity) is still unapproved. It needs a daily-count collector that does not exist, because `source_observations` hold only per-repo lifetime counts dated by `pushed_at`. The runner is task-agnostic infrastructure, run here on the synthetic demo set as a pipeline smoke test. Any ML in the product is a demo *readiness proxy score*, not outcome prediction. This is "non-outcome preparation intelligence".

**Recorded per run:** data sha256, feature schema version, target definition, label noise/seed, git revision (+dirty), Python/sklearn/pandas/numpy versions, seed, split protocol, model params, MAE/RMSE, bootstrap 95% CI over students, and a report checksum.

**Split.** `GroupKFold` by `student_id` (leave-one-student-out at n=8). Scaler, and any future selection/tuning/calibration, live inside the per-fold `Pipeline`. No untouched final test set exists at this n. The report says so. Do not tune against this evaluation.

**Baselines.** `mean` (naive), `rule_formula` (transparent weights, no learning), `ridge` (linear), `random_forest` (the shipped family). Primary metric: MAE, with skill vs `mean`.

**Reopen conditions.** Approve a task, collect real consented data, set the minimum sample from a power calculation, hold out a final test set (temporal if forecasting), and add the REFORMS checklist.

## B. Proposed research question (not approved, not implemented)

Status: **proposed; baseline and design need human approval before any model code** (exit gate). No metric thresholds are set here on purpose; they are fixed after the dataset is inspected and before the test set is touched.

### B1. Research question (one)

**RQ1.** For a student with a public GitHub account, can the number of **active weeks** (weeks with at least one contribution) in the next 4 weeks (0–4) be forecast from the preceding 12 weeks of daily contribution counts better than a persistence baseline?

Why this question: Path B has no outcome labels, but GitHub contribution history is real, dated, and has a natural future ground truth. It supports one product feature, a "consistency trend" insight, without any claim about placement.

### B2. Components

| Item | Definition |
|---|---|
| Problem statement | Forecast near-term engineering activity continuity from observed past activity. |
| User decision | Whether a student's practice habit is on track; which prompt to show ("your activity has dropped"). Not hiring/placement. |
| Hypothesis | A model using lagged weekly counts and simple recency features reduces MAE vs the best simple baseline by a margin larger than the across-user bootstrap uncertainty. Null: no improvement. A null result is an acceptable outcome. |
| Ground truth | Count of ISO weeks (0–4) in `(t, t+28d]` with ≥1 contribution, from the daily counts of `contributionsCollection.contributionCalendar` for the student's login (GitHub GraphQL). The calendar counts commits, issues, PRs and reviews, so the target is "active weeks", not "weeks with a commit". |
| Unit / population | Unit: (student, forecast date t). Population: consenting students with a public GitHub account and ≥1 contribution in the prior 12 weeks. Cannot be sized until recruitment. |
| Features at time t | Only days ≤ t: weekly contribution counts for 12 lagged weeks, weeks since last contribution. (Active-repo count is not in the calendar; it would need a separate source.) Optional later: LeetCode snapshot totals collected by PIS before t. No CGPA, no data fetched after t. |
| Exclusions | Bots, accounts younger than 12 weeks, users with private-only activity (cannot be observed). Report the excluded share. |
| Baselines | (1) Persistence: weeks active in the last 4 weeks. (2) Per-user historical mean over the 12 weeks, scaled to 4. (3) Seasonal-naive. (4) Poisson/ordinal regression on lagged counts. Then, only if (4) beats (1)–(3), a tree model. |
| Split | Temporal and group-aware. Train on forecast dates up to T1; validate (T1, T2]; hold out test (T2, T3]. Whole users are kept in one partition where sample size allows; otherwise report the user-leaking variant separately and label it. Leave a 28-day gap so labels in train do not overlap the test window. |
| Primary metric | MAE on weeks-active (0–4), reported as skill vs persistence = 1 − MAE_model / MAE_persistence, with user-level bootstrap CIs. Chosen because the target is a small ordinal count, MAE is interpretable in weeks, and persistence is the baseline a product could ship for free. |
| Secondary diagnostics | Per-user error distribution; error by activity level (inactive, sporadic, regular); calibration of P(active ≥1 week); performance on users with <12 weeks vs more; slice by account age; missing/private-activity share; confusion for "drops to 0" events (the costly case). |
| Minimum viable dataset | To be set after a pilot by variance of the target, not guessed now. As a gate: enough users that the bootstrap CI on skill is narrower than the effect worth acting on, and at least a few hundred users with ≥2 non-overlapping forecast windows is a placeholder, **unverified**, to be replaced by a power calculation. If recruitment cannot reach it, report descriptive baselines only. |
| Error costs | False "you are dropping off" nudges are mildly annoying; missing a real drop wastes the feature. Neither affects any placement decision. |

### B3. Research standard (applies to this and later experiments)

- **Baseline first.** Simple baselines are run and reported before any model; a complex model is justified only by beating them on the held-out period.
- **Leakage prevention.** Features computed strictly from data with timestamp ≤ t, enforced by one function that takes `t` and is unit-tested with a future-leak assertion. Scaling, feature selection, tuning, and calibration are fit inside training partitions. The test set is opened once. No random split used to improve numbers.
- **Reproducibility (FR-ML-004).** Record dataset snapshot hash, collection timestamps and sync-run IDs, feature-schema version, code commit, seeds, library versions, config, metrics, and artifacts. Raw API responses are stored so features can be recomputed.
- **Provenance filter.** Only `observed` data enters training. Synthetic, seed, and generated rows are excluded (CLAUDE.md safeguards).
- **Reporting.** Fill the REFORMS checklist ([arXiv:2308.07832](https://arxiv.org/abs/2308.07832)) for the final report.
- **Failure analysis.** Inspect the worst 5% of errors per slice, check for bots, bulk imports, and force-pushes inflating one week, and document rate-limit/partial-fetch cases.
- **Claim boundary.** Results say only "forecasts next-4-week GitHub activity for this population". They do not support any placement claim. No accuracy target is set in advance.

### B4. Data collection prerequisites (not done)

1. Collector: GitHub GraphQL `contributionsCollection.contributionCalendar` (daily counts) with a server-side token, never sent to clients. Replaces per-repo REST paging, which cannot give dated commits cheaply. Not implemented. Needs consent and provenance records (daily aggregate; no invented timestamps).
2. Consent text covering research use (PRD §19 #14), separate from product use.
3. A pilot to measure request cost and target variance.
4. **Still unverified** (check against GitHub docs and a real account before relying on any):
   - **Window limit**: maximum span of one `contributionsCollection` query (believed about one year, unconfirmed) and whether 12+4 weeks needs several calls.
   - **Timezone**: which timezone defines a calendar day and a week boundary.
   - **Private contributions**: whether and when they appear in the calendar for a public-username connection, and how to detect the undercount.
   - **ToS / API terms**: use of the data for research, and retention.

### B5. Fallback

If the pilot cannot reach a defensible sample, ship rule-based, provenance-labelled gap detection only and document that no ML task was validated. Path A remains closed without real outcome labels.

### B6. Decisions requiring human approval

1. RQ1 as the first ML task (vs deferring ML).
2. Baseline set and split design above.
3. Consent and recruitment route (own students? institution?).
4. Use of LeetCode snapshots as optional features, subject to ToS review.
