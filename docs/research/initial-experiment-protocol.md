# Phase 2 — Initial Experiment Protocol

Status: **proposed; baseline and design need human approval before any model code** (exit gate). No metric thresholds are set here on purpose; they are fixed after the dataset is inspected and before the test set is touched.

## 1. Research question (one)

**RQ1.** For a student with a public GitHub account, can the number of weeks with at least one self-authored commit in the next 4 weeks (0–4) be forecast from the preceding 12 weeks of self-authored commit history better than a persistence baseline?

Why this question: Path B has no outcome labels, but GitHub author-filtered commit history is real, timestamped, and has a natural future ground truth. It supports one product feature, a "consistency trend" insight, without any claim about placement.

## 2. Components

| Item | Definition |
|---|---|
| Problem statement | Forecast near-term engineering activity continuity from observed past activity. |
| User decision | Whether a student's practice habit is on track; which prompt to show ("your activity has dropped"). Not hiring/placement. |
| Hypothesis | A model using lagged weekly counts and simple recency features reduces MAE vs the best simple baseline by a margin larger than the across-user bootstrap uncertainty. Null: no improvement. A null result is an acceptable outcome. |
| Ground truth | Count of ISO weeks (0–4) in `(t, t+28d]` with ≥1 commit whose author matches the student's GitHub login, taken from the List-commits API with `author`, `since`, `until`. |
| Unit / population | Unit: (student, forecast date t). Population: consenting students with a public GitHub account and ≥1 authored commit in the prior 12 weeks. Cannot be sized until recruitment. |
| Features at time t | Only commits with timestamp ≤ t: weekly authored counts for 12 lagged weeks, weeks since last commit, number of active repos. Optional later: LeetCode snapshot totals collected by PIS before t. No CGPA, no data fetched after t. |
| Exclusions | Forked-only activity without authored commits, bots, accounts younger than 12 weeks, users with private-only activity (cannot be observed). Report the excluded share. |
| Baselines | (1) Persistence: weeks active in the last 4 weeks. (2) Per-user historical mean over the 12 weeks, scaled to 4. (3) Seasonal-naive. (4) Poisson/ordinal regression on lagged counts. Then, only if (4) beats (1)–(3), a tree model. |
| Split | Temporal and group-aware. Train on forecast dates up to T1; validate (T1, T2]; hold out test (T2, T3]. Whole users are kept in one partition where sample size allows; otherwise report the user-leaking variant separately and label it. Leave a 28-day gap so labels in train do not overlap the test window. |
| Primary metric | MAE on weeks-active (0–4), reported as skill vs persistence = 1 − MAE_model / MAE_persistence, with user-level bootstrap CIs. Chosen because the target is a small ordinal count, MAE is interpretable in weeks, and persistence is the baseline a product could ship for free. |
| Secondary diagnostics | Per-user error distribution; error by activity level (inactive, sporadic, regular); calibration of P(active ≥1 week); performance on users with <12 weeks vs more; slice by account age; missing/private-activity share; confusion for "drops to 0" events (the costly case). |
| Minimum viable dataset | To be set after a pilot by variance of the target, not guessed now. As a gate: enough users that the bootstrap CI on skill is narrower than the effect worth acting on, and at least a few hundred users with ≥2 non-overlapping forecast windows is a placeholder, **unverified**, to be replaced by a power calculation. If recruitment cannot reach it, report descriptive baselines only. |
| Error costs | False "you are dropping off" nudges are mildly annoying; missing a real drop wastes the feature. Neither affects any placement decision. |

## 3. Research standard (applies to this and later experiments)

- **Baseline first.** Simple baselines are run and reported before any model; a complex model is justified only by beating them on the held-out period.
- **Leakage prevention.** Features computed strictly from data with timestamp ≤ t, enforced by one function that takes `t` and is unit-tested with a future-leak assertion. Scaling, feature selection, tuning, and calibration are fit inside training partitions. The test set is opened once. No random split used to improve numbers.
- **Reproducibility (FR-ML-004).** Record dataset snapshot hash, collection timestamps and sync-run IDs, feature-schema version, code commit, seeds, library versions, config, metrics, and artifacts. Raw API responses are stored so features can be recomputed.
- **Provenance filter.** Only `observed` data enters training. Synthetic, seed, and generated rows are excluded (CLAUDE.md safeguards).
- **Reporting.** Fill the REFORMS checklist ([arXiv:2308.07832](https://arxiv.org/abs/2308.07832)) for the final report.
- **Failure analysis.** Inspect the worst 5% of errors per slice, check for bots, bulk imports, and force-pushes inflating one week, and document rate-limit/partial-fetch cases.
- **Claim boundary.** Results say only "forecasts next-4-week GitHub activity for this population". They do not support any placement claim. No accuracy target is set in advance.

## 4. Data collection prerequisites (not done in Phase 2)

1. Author-filtered commit collector with consent and provenance records.
2. Consent text covering research use (PRD §19 #14), separate from product use.
3. A pilot to measure request cost, unlinked-email loss, and target variance.

## 5. Fallback

If the pilot cannot reach a defensible sample, ship rule-based, provenance-labelled gap detection only and document that no ML task was validated. Path A remains closed without real outcome labels.

## 6. Decisions requiring human approval

1. RQ1 as the first ML task (vs deferring ML).
2. Baseline set and split design above.
3. Consent and recruitment route (own students? institution?).
4. Use of LeetCode snapshots as optional features, subject to ToS review.
