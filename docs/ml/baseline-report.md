# Baseline report (synthetic smoke test)

**Not evidence about placement.** Labels are a formula of the inputs plus noise; n = 8 demo students. Produced by `python -m ml.experiment`. The JSON in `experiments/` holds the full record. Dataset sha256 prefix `a7d069146a57`; leave-one-student-out CV; seed 42.

| Model | MAE | 95% CI (student bootstrap) | Skill vs mean |
|---|---|---|---|
| mean | 24.77 | 15.5 – 34.5 | 0.00 |
| rule_formula | 9.76 | 3.7 – 17.5 | 0.61 |
| ridge | 6.38 | 4.1 – 8.5 | 0.74 |
| random_forest | 7.76 | 4.0 – 12.6 | 0.69 |

**Reading.** Models beat the mean because the target is built from the inputs. The CIs for ridge and random forest overlap heavily, so no model ranking is supported. The rule formula's MAE of 9.8 even though it contains the label weights comes from in-fold scaling differing from the full-data scaling used to build labels, plus the N(0,5) noise. A linear model fits best, which is expected for a linear formula. **This does not show the random forest is the right model.**

**Supported:** the runner, split and baselines work and are reproducible. **Not established:** any predictive validity, any model superiority, any placement relationship. **What would help:** real consented data, an approved target (RQ1 or outcome labels), and a power-based sample size.
