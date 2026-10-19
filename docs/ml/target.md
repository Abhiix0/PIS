# Product Target and Assessment Semantics

Status: **proposed, needs human sign-off** (see §6). Access date for all web sources: 2026-10-13.

## 1. Decision

**Path B — transparent preparation intelligence.** PIS does not claim to predict placement, hiring, or a "placement probability". Path A is not feasible on current evidence (§2).

## 2. Why Path A is not feasible

Repo facts are verified (initial repo audit). Feasibility judgments about the outside world are hypotheses.

| Requirement for A | Evidence today |
|---|---|
| Real historical outcome labels | None. The repo has 8 hand-written seed students (`sql/seed.sql`). Labels in `ml/labels.py` are a weighted formula of the same features plus N(0,5) noise. |
| Labels timed after features | Not applicable: no outcomes exist. |
| Consent / access | No mechanism. No auth (D-12), no research-consent flow (PRD §19 #14 open). Outcomes (offers, employers, salary) are sensitive and would come from placement cells or the students themselves. |
| Representative population | Unknown. One institution's cohort is one cohort, one year, one market. Selection bias is likely (who has a public GitHub/LeetCode, who sits for drives). |
| Size | Unknown. The only public placement datasets found are ~215 rows of academic/demographic fields with no GitHub/LeetCode features (see literature doc). Not enough to evaluate a model on PIS features. |

Reopen Path A only if an institution supplies per-student, timestamped outcomes under a data agreement **and** features can be reconstructed as of a date before the outcome. GitHub commit history can be; LeetCode aggregates cannot (see data-source doc).

## 3. Assessment semantics (recommended)

- Name it **"Preparation assessment"** / **"readiness proxy score"**. Never "placement probability", "chance of getting placed", or "prediction of hiring".
- The existing 0–100 score is a weighted formula of five features. Until replaced, UI/API must describe it as a heuristic summary, not a learned or validated outcome.
- Every displayed metric carries a provenance class (`observed` | `user_entered` | `aggregate` | `inferred` | `synthetic`), a collection timestamp, and freshness (FR-INT-006/008).
- Missing states are distinct: `not_connected`, `unavailable`, `stale`, `error`, genuine `0` (FR-DATA-003).
- Synthetic/demo data appears only in a visibly labelled demo mode and is never merged into a real user's assessment.
- Gap detection and recommendations are rule-based and state their rule and source ("Fewer than 2 active weeks in the last 90 days, from GitHub commits you authored").
- ML is allowed only for tasks with an observable ground truth (see experiment protocol). Claims are limited to that task.

## 4. User decision supported

A student deciding **what to practise next** and whether their activity is trending up or down. Not an institution ranking students, and not a hiring decision (non-goal until authorised cohort use is decided, PRD §19 #13).

## 5. Error costs

- An overstated score gives false reassurance or the wrong prep emphasis. An understated one discourages, and it penalises students whose work is private or off-platform.
- Mitigation: show coverage ("based on public GitHub + LeetCode counts only"), show uncertainty, never rank individuals.

## 6. Decisions and unresolved items

Proposed in `../architecture/decisions/0005-ml-direction.md` (needs human sign-off):

1. Path B and the wording rules above (PRD §19 #1). Outcome prediction closed; reopen conditions are in the ADR.
2. The first ML task is RQ1 in `experiment-protocol.md` §B: forecast **active weeks** in the next 4 weeks from daily GitHub contribution counts. Isolated offline experiment, not wired into the product score.
3. The legacy RandomForest score is a heuristic proxy, quarantined from the real-user path. UI copy relabelled "Demo formula score" (ADR 0005, 2026-10-19); full retirement (API field) still open.

Still unresolved:

4. GitHub: public username only vs OAuth device flow (§19 #3). Recommendation: public-only first, OAuth later. RQ1's collector (GraphQL calendar, server token) has unverified points: window limit, timezone, private contributions, ToS (protocol §B4).
5. LeetCode: keep the integration only as labelled aggregates, or use manual entry. ToS not verified (§19 #4).
6. Whether any placement outcomes will ever be collected, from whom, with what consent (§19 #14, #13).
7. Consent and recruitment route for RQ1 (protocol §B6).
