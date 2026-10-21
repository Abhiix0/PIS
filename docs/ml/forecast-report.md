# Forecast report (RQ1): next-4-week active weeks

**Status: pipeline built and tested; NOT run on real data. No forecasting result exists.** No research export (`ml/forecast/export.py` output) has been collected, and synthetic data is not substituted. Every result cell below is empty on purpose. This is not evidence about forecastability, and it is never evidence about placement.

Command (when an export exists):

```bash
python -m ml.forecast.run --data <daily_*.csv> [--out experiments]            # train + validation only
python -m ml.forecast.run --data <daily_*.csv> --open-test                    # opens the final test, once per dataset
```

Output: `experiments/forecast-<data-hash12>.json` (dataset sha256, git revision, library versions, seed 42, split, metrics, `report_sha256`). `--open-test` writes `experiments/forecast-test-opened-<hash12>.lock`; a second `--open-test` on the same data is refused.

## Design as implemented

| Item | Implementation |
|---|---|
| Origins | One per (user, Sunday `t`). Needs all 84 days before and 28 days after `t` observed (`present`/`measured_zero`); missing days are never filled with 0. Needs ≥1 contribution in the 12 weeks. |
| Target | `y` = ISO weeks (Mon–Sun) in `(t, t+28d]` with ≥1 contribution, 0–4. |
| Features | 12 weekly sums from days ≤ `t`, via `features_as_of` (one function; the leakage test edits the future and checks features are unchanged). |
| Split | Users shuffled (seed 42) 60/20/20, origins cut at the 60th/80th percentile dates T1/T2. Train: `t+28d ≤ T1`. Val: `t > T1`, `t+28d ≤ T2`. Test: `t > T2`. Users and time both disjoint, 28-day gap. If any partition has under 20 users (placeholder, **unverified**; to be set by power calculation) the run falls back to **time-forward only, users may repeat**, and the JSON and report label it `WEAKER`. |
| Baselines | persistence (active weeks in last 4), user mean (active share of 12 weeks × 4), seasonal-naive (the same 4-week window shifted back 8 weeks; a 4-week period would equal persistence), Poisson regression on log1p lagged counts (fixed alpha 1.0, no tuning). Ordinal regression was **not** implemented. All predictions rounded and clipped to 0–4. |
| Tree model | **Not implemented.** Gate (reported in JSON `tree_gate`): Poisson beats the best simple baseline on validation with the 95% user-bootstrap CI of the MAE difference entirely below 0. |
| Metrics | MAE; skill = 1 − MAE/MAE_persistence; 1000-rep user-level bootstrap CIs; drop-to-zero precision/recall (candidates: persistence > 0; event: `y` = 0; called: prediction 0). |
| Failure analysis | Worst 5% absolute errors for the best model per slice (activity level, recent activity). Bulk-import flag: any day ≥ 100 contributions. Bot-like flag: ≥ 7 consecutive days with identical count ≥ 10. Both are **heuristics, unverified** against real accounts; the calendar cannot identify bots or force-pushes. |

## Results

| Partition | Variant | Users | Origins | Best MAE | Skill vs persistence (CI) | Tree gate |
|---|---|---|---|---|---|---|
| validation | not run | – | – | – | – | – |
| test | not opened | – | – | – | – | – |

## REFORMS-style checklist ([arXiv:2308.07832](https://arxiv.org/abs/2308.07832))

| Module | Item | Answer |
|---|---|---|
| 1 Study goals | Claim and population | Forecast next-4-week active weeks for consenting users with public GitHub accounts. No placement claim. Population unknown until recruitment. |
| 2 Computational reproducibility | Code, data, versions | Code in repo; data hash, git revision (+dirty), versions, seed in JSON. Data itself is not committed. Run reproducibility is tested (same data → same `report_sha256`). |
| 3 Data quality | Source, size, missingness | GitHub contribution calendar via the consented export. Size: none yet. Missing days drop origins; private-only contributions are undercounted (undetectable here). Timezone and window limits: **unverified**. |
| 3 | Outliers, bots | Heuristic flags only; no exclusion applied. |
| 4 Data preprocessing | Exclusions | The export (`ml/forecast/export.py`) drops only rejected, unobserved or non-consented rows and keeps `stale` rows with their `value_state`. `run.py` `load_daily` then drops every row whose `value_state` is not `present`/`measured_zero` (so `stale` rows are excluded there, not in the export). Origins are dropped when the 12-week history plus 4-week horizon has a missing day, or when the 12-week history sums to 0 (per origin, not per user). Excluded share is not reported by the code yet. |
| 5 Modeling | Baselines, tuning | Four baselines; Poisson with fixed alpha; no tuning, so no tuning leakage. |
| 6 Data leakage | Feature time, split | Features use days ≤ `t`; users disjoint across partitions in the strict variant; 28-day gap; scaler fit inside the pipeline on train; test opened once (lock file). Overlapping weekly origins within a user are dependent; the bootstrap resamples users. |
| 7 Metrics and uncertainty | Metric, CI | MAE and skill vs persistence, user-level bootstrap. No power calculation; sample size is a placeholder. |
| 8 Generalizability | Limits | One platform, consenting volunteers, calendar-day counts include issues/PRs/reviews. Does not transfer to other populations or to outcomes. |

## Known limitations

- Bootstrap CIs assume enough users; with few users they are not trustworthy.
- `MIN_USERS_PER_PARTITION`, bulk and bot thresholds are unvalidated placeholders.
- Seasonal-naive with a weekly or term period is not tested; the 12-week history allows only the 8-week shift.
- Ordinal regression and tree models: not run.
