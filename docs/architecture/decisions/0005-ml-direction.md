# ADR 0005 — ML direction: preparation intelligence, RQ1 as an isolated offline experiment

Status: **proposed** (needs owner sign-off; `docs/ml/target.md` §6 and `docs/ml/experiment-protocol.md` §B6). Nothing here is implemented by this ADR.

## Context
- No real placement outcomes exist. `sql/seed.sql` has 8 hand-written students; labels in `ml/labels.py` are a weighted formula of the same features plus N(0,5) noise (`docs/ml/target.md` §2).
- The shipped RandomForest learns that formula, not outcomes.
- GitHub activity is real and dated, so a next-4-week "active weeks" forecast has an observable ground truth (RQ1, `docs/ml/experiment-protocol.md` §B). The current collector stores only per-repo lifetime counts dated by `pushed_at`, so RQ1 cannot be run yet.

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

## Promotion gate (set 2026-10-19, before any test result exists)
Promote a forecast model only if the skill-vs-persistence 95% user-bootstrap CI lower bound on the opened test is > 0 (`docs/ml/forecast-report.md`).
- **Pass**: propose, do not implement, a bundle promotion via `ml/bundle.py` (candidate -> approve -> activate) with smoke test and rollback; list changed product copy.
- **Fail or inconclusive**: ship rules only; keep `ml/forecast/` code.

## Outcome (2026-10-19): inconclusive — rules only
`ml/forecast/run.py` has not been run on real data; no research export exists, and synthetic data is not substituted. There is no CI, so the gate is not passed. Result: no forecast model ships; product stays rule-based and provenance-labelled. This is a missing result, not evidence that forecasting fails. Re-run the gate when a consented export exists.

## Legacy RF score: relabelled, not retired
Retiring needs API/schema changes (`readiness_score` is in `/api/v1/assessments` and the client types) and is deferred. UI copy now says "Demo formula score (legacy model, not a prediction)"; the old "ML estimate" wording is removed. Real users still get `insufficient_evidence`.

## Open items
1. Owner approval of RQ1, baselines and split design.
2. Recruitment and consent route.
3. Retire the legacy RF score fully (API field and demo path).
