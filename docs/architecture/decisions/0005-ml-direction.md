# ADR 0005 — ML direction: preparation intelligence, RQ1 as an isolated offline experiment

Status: **Path B and wording approved 2026-10-24; RQ1 approval and consent route still OPEN** (see `docs/ml/target.md` §6 and `docs/ml/experiment-protocol.md` §B6). Nothing here is implemented by this ADR.

## Context
- No real placement outcomes exist. `sql/seed.sql` has 8 hand-written students; labels in `ml/labels.py` are a weighted formula of the same features plus N(0,5) noise (`docs/ml/target.md` §2).
- The shipped RandomForest learns that formula, not outcomes.
- GitHub activity is real and dated, so a next-4-week "active weeks" forecast has an observable ground truth (RQ1, `docs/ml/experiment-protocol.md` §B). The default collector stores only per-repo lifetime counts dated by `pushed_at`. A daily-calendar collector exists, `fetch_github_calendar_observations` in `ingest/github_api.py` (GraphQL, last 365 UTC days, stored as `github_contribution_day`), but it is flag-gated by `GITHUB_CALENDAR_ENABLED` (default off) and needs a server `GITHUB_TOKEN`. No consented export has been run, so RQ1 has no data yet.
- `features/as_of.py` `activity_trend` is a deterministic trend rule over weekly counts, wired into `app/routers/v1.py` (`activity_trend` block). It uses no model and produces no score.

## Decision
1. **Path B**: PIS is transparent preparation intelligence. It makes no placement or hiring claim.
2. **RQ1 is the only candidate ML task**, run as an isolated offline experiment (own script and data snapshot, `experiments/` output). It does not feed the product score or any API route until it passes its pre-registered evaluation and a human approves promotion.
3. **Outcome prediction is closed.** Reopen only if all hold:
   - an institution supplies per-student, timestamped outcomes under a data agreement;
   - consent covers research use (PRD §19 #14);
   - features can be rebuilt as of a date before each outcome;
   - sample size is set by a power calculation and a final held-out set exists.
4. **The legacy RandomForest readiness score is a heuristic proxy**, labelled as such wherever shown. It is quarantined from the real-user path: real users get `insufficient_evidence` from `POST /api/v1/assessments`, not that score. It is kept only for the local/demo path until retired.

## Consequences
- Product ML claims stay limited to "readiness proxy score" (CLAUDE.md safeguard).
- RQ1 needs a new collector, consent text and a pilot first (protocol §B4). None exist.
- If the pilot cannot reach a defensible sample, ship rule-based, provenance-labelled gap detection only (protocol §B5).

## Promotion criterion (owner decision 2026-10-22, pre-registered before any result exists)
Replaces the earlier CI-only gate. On the opened user-disjoint test set (`docs/ml/forecast-report.md`), with skill = 1 - MAE_model / MAE_persistence, promote a forecast model only if **both** hold:
- skill >= 0.10;
- the lower bound of the user-level 95% bootstrap CI of skill is > 0.

Otherwise ship rules only. No tree or other complex model unless the existing `tree_gate` (`ml/forecast/run.py`) passes.
- **Pass**: propose, do not implement, a bundle promotion via `ml/bundle.py` (candidate -> approve -> activate) with smoke test and rollback; list changed product copy.
- **Fail or inconclusive**: ship rules only; keep `ml/forecast/` code.
- `ml/forecast/run.py` evaluates this gate (`promotion_check`, added 2026-10-24) and writes `promotion_check` into every report: `pass`, `fail`, or `inconclusive` when the test set was not opened or skill/CI is not computable. `python -m ml.forecast.run --check <report.json>` re-applies it to a saved report. Unit-tested; never run on real data.

## Outcome (2026-10-19): inconclusive — rules only
`ml/forecast/run.py` has not been run on real data; no research export exists, and synthetic data is not substituted. There is no CI, so the gate is not passed. Result: no forecast model ships; product stays rule-based and provenance-labelled. This is a missing result, not evidence that forecasting fails. Re-run the gate when a consented export exists.

## Legacy RF score: relabelled, not retired
Retiring needs API/schema changes (`readiness_score` is in `/api/v1/assessments` and the client types) and is deferred. UI copy now says "Demo formula score (legacy model, not a prediction)"; the old "ML estimate" wording is removed. Real users still get `insufficient_evidence`.

## Open items
1. Owner approval of RQ1, baselines and split design.
2. Recruitment and consent route.
3. Retire the legacy RF score fully (API field and demo path).
