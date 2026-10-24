# Intelligence and evaluation specification

Status: **draft specification, not implemented, not validated.** Docs only. Path B (`../ml/target.md`) is itself "proposed, needs human sign-off". Every number below is **proposed** unless it is quoted from code, and quoted code values are product choices, not validated ones.

Sources read for this file: `../ml/target.md`, `decisions/0005-ml-direction.md`, `../ml/experiment-protocol.md`, `domain-model.md`, `../data/provenance.md`, `../data/data-dictionary.md`, `../research/github-calendar-spike.md`, `../../features/as_of.py`, `../../apps/desktop/src/lib/assessment.ts`, `../../app/routers/v1.py` (`_build_evidence`, `create_assessment`).

## 0. Owner decisions for this unit

Recorded 2026-10-24 from the owner's instruction to use the roadmap defaults. Decisions not listed as Approved are OPEN.

| # | Decision | Status |
|---|---|---|
| 1 | Path B + wording rules approved? | **Approved 2026-10-24**: no placement or hiring predictions. |
| 2 | Composite score or dimension-level evidence states only? | **Approved 2026-10-24**: no composite for the MVP; dimension-level states only (§3). |
| 3 | Store CGPA? | **Approved 2026-10-24**: optional, self-reported context only (D4). Excluded from evidence states and recommendations. |
| 4 | LeetCode: keep vs manual entry? | **Approved 2026-10-24**: stays disabled (`LEETCODE_INTEGRATION_ENABLED=false`) until the owner reads the ToS. Manual entry is not specified. |
| 5 | GitHub scope: public-only vs OAuth later? | **Approved 2026-10-24**: public username only for the MVP; existing calendar flags unchanged; OAuth later. |
| 6 | Consent / recruitment route for RQ1 | **Approved 2026-10-24** (separate opt-in); forecasting research deferred until consent text, recruitment and data exist. |
| 7 | Dimensions in v1 | **Approved 2026-10-24**: D1 activity, D2 project footprint, D3 LeetCode (flag-gated, off), D4 CGPA as context only. |
| 8 | Identity provider | OPEN. Clerk is to be evaluated against loopback PKCE on any port, `offline_access` and a role claim; otherwise another OIDC provider. Not verified (Phase 3.2). |

Outside this spec: AWS region is OPEN (depends on the free-host comparison); infrastructure budget is $0/month; signing is unsigned pilot with manual GitHub Releases (roadmap decisions 9, 10, 12).

Consequence: `../ml/target.md` §6 and ADR 0005 record the same approvals. Nothing here is implemented or validated; the numbers below stay "proposed".

## 1. Dimensions (v1 set approved; contents proposed)

Current behaviour: real accounts get `assessment_type = 'insufficient_evidence'` and no score (`app/routers/v1.py` `create_assessment`, `NO_SCORE_REASON`). `_build_evidence` (`evidence-v1`) already assembles per-provider evidence blocks. The dimensions below organise that evidence; none is a new score.

Wording rule (from `../ml/target.md` §3): "preparation assessment" / "readiness proxy score"; never "placement probability" or any hiring claim.

### D1 GitHub activity consistency
| Item | Content |
|---|---|
| Observable evidence | `github_contribution_day` (one per UTC day, `granularity=event`, precision `day`). Derived by `features/as_of.py`: `weekly_counts` (12 weeks), `weeks_since_last_active`, `active_days_28d`, and the `activity_trend` rule (`active_weeks_last_4`, `active_weeks_prev_8`, `direction`). |
| Can state | Which of the last 12 weeks had ≥1 contribution; whether active weeks in the last 4 are up, down or flat versus the prior 8 (per-week rate rule, `activity_trend`). |
| Cannot establish | Skill, code quality, effort or hours. The calendar counts commits, issues, PRs and reviews (`../ml/experiment-protocol.md` §B2). Private work is undercounted or invisible; the setting-dependent behaviour for third-party users is unverified (`../research/github-calendar-spike.md`). Day assignment timezone is unverified. Says nothing about hiring or placement. |
| Provenance class | `observed` (calendar); trend output is a derived rule result. |
| Collection source | GitHub GraphQL `contributionCalendar`, last 365 UTC days, server `GITHUB_TOKEN`, off unless `GITHUB_CALENDAR_ENABLED=true`; staging/production also need `GITHUB_CALENDAR_APPROVED=true` (`../data/provenance.md`). |

### D2 GitHub project footprint
| Item | Content |
|---|---|
| Observable evidence | `github_public_repo_count`; `github_repo_commit_count` (per repo, summed by `_build_evidence` into `commits_in_sampled_repos`, with `repos_sampled`). |
| Can state | Number of public non-fork repos (capped at 10 enumerated); commits authored by the username in the newest-pushed sampled repos. |
| Cannot establish | A daily rate or recency of commits: `event_at` is the repo's `pushed_at` (precision `repo_push`), not a commit date. Commits under unlinked emails are excluded. Not a measure of project quality. Private repos are invisible. |
| Provenance class | `observed`, `granularity=aggregate`. |
| Collection source | GitHub REST, public username, no user token (`../data/provenance.md`). |

### D3 LeetCode practice volume
| Item | Content |
|---|---|
| Observable evidence | `leetcode_solved_easy`, `leetcode_solved_medium`, `leetcode_solved_hard`; `apps/desktop/src/lib/assessment.ts` consumes `leetcode_solved_all`, but the backend does **not** emit it today (only `_easy/_medium/_hard`; verified by grep). Phase 3.1 adds it as a derived sum when all three are present. |
| Can state | Accepted-problem counts by difficulty at fetch time. |
| Cannot establish | When problems were solved, so no consistency or trend (`consistency_score` is "not computable for real LeetCode users", data dictionary). Not problem-solving ability or interview performance. |
| Provenance class | `observed`, `granularity=aggregate`, `event_at` NULL (precision `unknown`); time = `collected_at` only. |
| Collection source | Unofficial LeetCode GraphQL; disabled by default (`LEETCODE_INTEGRATION_ENABLED=false`); ToS unverified. Contingent on decision 4. |

### D4 Academic (context only, decision 3)
| Item | Content |
|---|---|
| Observable evidence | `profiles.cgpa`, 0–10 (`../data/data-dictionary.md`). Not a `source_observations` row today ("user-entered CGPA as an observation" is listed under "Not done", `../data/provenance.md`). `_build_evidence` carries it as `{value, provenance: "user_entered"}`. |
| Can state | The value the student entered, labelled self-reported. |
| Cannot establish | That it is verified, or comparable across institutions or scales. |
| Provenance class | `user_entered`. |
| Collection source | Profile form. Domain model: "CGPA retained only if justified (PRD §19#5)". Decision 3: context only, never counted as evidence or used in recommendations. |

## 2. Missing, stale and zero semantics

Enums (from `domain-model.md` §3): `provenance` = `observed | user_entered | derived | inferred | synthetic`; `value_state` = `present | not_collected | source_failed | stale | measured_zero`. CHECKs: a NULL is never a zero and a zero is never a missing value; `measured_zero` ⇒ value 0.

| Situation | `value_state` | Evidence-state wording | Status today |
|---|---|---|---|
| Value observed, > 0 | `present` | value shown with provenance and timestamp | adapters write it |
| Provider reported 0 (e.g. account with no repos; calendar day with 0) | `measured_zero` | "0, reported by the provider" | adapters write it (`../data/provenance.md`) |
| Provider not connected / never synced | `not_collected` | "not connected" | `_build_evidence` returns `None` for the provider block; no row exists |
| Sync failed | `source_failed` | "last sync failed (code)" | a failed request stores nothing; the run holds a safe error code, not an observation. Mapping to a displayed state is not implemented in `_build_evidence`. |
| Calendar day absent from response | none (no row) | unknown, never filled as zero; run is `partial` | `features/as_of.py`: absent day ⇒ `None`; any value needing it is `None` |
| Older than the staleness window | `stale` | "last import over N days ago" | **Not done server-side**: stale marking is listed under "Not done" (`../data/provenance.md`). The client computes it from `synced_at` (`isStale`, `STALE_DAYS = 7`). |
| Synthetic/demo | provenance `synthetic` | visibly labelled demo, never merged into a real assessment | `../ml/target.md` §3 |
| Aggregate with unknown time | `present`, precision `unknown` | no date claims | LeetCode |

Inconsistencies found (for the owner, not resolved here):
- `../ml/target.md` §3 lists provenance classes as `observed | user_entered | aggregate | inferred | synthetic`; `domain-model.md` §3 lists `derived` instead of `aggregate` and carries aggregate-ness in `granularity`. This spec follows `domain-model.md`.
- `_build_evidence` does not select `value_state`, and sets each block's `provenance` from `rows[0]` (an arbitrary row of the latest run, no ORDER BY in the query as read). Mixed provenance within a block is therefore not guaranteed to show its weakest class, contrary to the data-dictionary rule "weakest provenance of its input rows" (stated there for legacy features). Unverified in a test.
- The trend `as_of` is `max(days)` (latest calendar day returned), not the sync time.

## 3. Output contract per dimension

No composite number (decision 2, approved): this contract defines per-dimension states only.

Each dimension returns one object:

| Field | Content |
|---|---|
| `dimension` | D1–D4 id |
| `evidence_state` | one of `no_evidence` (not connected / never synced), `stale`, `partial` (e.g. calendar missing days, repo cap hit), `sufficient`, `source_failed`. Names are **proposed**; the repo today has only the assessment type `insufficient_evidence` and the per-value states above. |
| `values[]` | each: name (existing `observation_type` or derived name), value, `provenance`, `value_state`, `event_at` precision, `collected_at`/`synced_at`, `sync_run_id` |
| `rule` | id and text of the rule that fired, e.g. `activity_trend`: "active weeks, last 4 vs previous 8" (already emitted by `_build_evidence`, with `as_of`, `features_version`) |
| `coverage` | one line naming sources and limits, e.g. "public GitHub, newest 10 non-fork repos, contributions visible to a public profile" (shape of `../ml/target.md` §5) |
| `caveats[]` | from §1 "Cannot establish" for the dimension; plus current data-quality rejections (`/me/data-quality`) |

Recommendations (priorities) stay rule-based with the evidence field cited, as in `priorities()` in `apps/desktop/src/lib/assessment.ts` (each returns `id`, `text`, `evidence`). Example rules already present there: no provider data; CGPA missing; provider stale; `github_public_repo_count = 0`; `leetcode_solved_all = 0`. Those rules and their copy are editorial and unreviewed (§6 tier 5).

If decision 2 later selects a composite: weights would be labelled "proposed, unvalidated"; tested by (a) the monotonicity and missing-data checks in §6 tier 3, (b) sensitivity analysis showing rank/category changes under weight perturbation, (c) expert review of category boundaries. No outcome data exists to fit weights, so they could never be called learned or validated from outcomes (`../ml/target.md` §2).

## 4. Parameters (all proposed)

| Parameter | Proposed value | Origin | Test that would change it |
|---|---|---|---|
| Staleness window, provider data | 7 days | existing `STALE_DAYS` in `assessment.ts`, described there as "a product choice, not a model property" | Consented sync history: distribution of day-to-day change in each evidence value; pick the window where unseen change exceeds a stated tolerance. Expert/student review of the nudge. |
| Calendar completeness for trend | all 12 weeks present, else direction `None` | existing `activity_trend` / `WEEKS = 12` (`as-of-v1`) | Sensitivity of `direction` to allowing ≤k missing days, on consented calendars. |
| Trend comparison | last 4 weeks vs prior 8, per-week rate (`2a > b` ⇒ up) | existing rule | Golden fixtures (tier 3); agreement with expert-labelled trajectories. |
| Minimum evidence for `sufficient` | at least one provider run succeeded and not stale | proposed here, no repo value | Expert review of when a statement becomes misleading; error review on real accounts. |
| Repo sample cap | 10 newest-pushed non-fork repos | existing adapter limit (`../data/provenance.md`) | Compare against full-repo counts on consented accounts; the cap truncates the footprint. |
| Calendar window | 365 UTC days | existing; spike verified 365/366 accepted, 400 rejected | Re-run of the spike (status: not run on 2026-10-22). |
| Example gap threshold "fewer than 2 active weeks in the last 90 days" | not adopted | appears in `../ml/target.md` §3 as an example wording only | Would need a documented rationale and expert review before use. |

None of these is validated.

## 5. Deterministic vs statistical vs ML

| Component | Allocation | Reason |
|---|---|---|
| Evidence collection, validation, quarantine | Deterministic | Typed adapters, allow-list validators (`../data/provenance.md`). |
| Missing/stale/zero state assignment | Deterministic | Must be auditable; CHECK-enforced. |
| Weekly counts, `weeks_since_last_active`, `active_days_28d`, `activity_trend` | Deterministic | Pure functions of days ≤ t (`features/as_of.py`); no model, no score. |
| Gap detection and recommendations | Deterministic rules, each citing its evidence | Required by `../ml/target.md` §3; traceability. |
| Uncertainty / coverage statements | Deterministic text from state | No data to calibrate anything statistical. |
| Descriptive statistics (e.g. error distributions in evaluation) | Statistical | Used in evaluation only; not user-facing claims. |
| Forecast of active weeks (RQ1) | ML candidate, offline only | Only task with an observable ground truth (ADR 0005). Not wired into any route. Tree models only if `tree_gate` passes (`ml/forecast/run.py`, per ADR 0005). |
| Legacy RandomForest "readiness" score | Heuristic proxy, quarantined to demo | Learns a formula plus N(0,5) noise on ~8 students, not outcomes (ADR 0005). |
| Placement/hiring prediction | None | Closed; reopen conditions in ADR 0005. |

## 6. Evaluation framework

Tiers are separate; passing one does not imply another. No sample size is stated anywhere in this document: each comes from a power calculation done after a pilot.

### Tier 1: software correctness
- Unit/integration tests for adapters, validators, sync lifecycle, schema invariants, the `as_of` point-in-time rule (future-leak assertion, required by `../ml/experiment-protocol.md` §B3), and SQL parity (`tests/test_migrate.py::test_full_and_single_feature_sql_agree`).
- Earlier test and coverage counts are in `audit-report.md`; **not read for this spec**, so none are quoted. Live-network provider behaviour is unverified (`../data/provenance.md`).
- Passing means "behaves as coded", nothing about usefulness.

### Tier 2: data quality
- Quarantine rates by rule code (`/me/data-quality`), sync success/partial/failed rates, completeness of the 365-day calendar, share of accounts with private-only activity (undetectable today).
- Known unverified: timezone day assignment, private-contribution behaviour for third parties, GraphQL error type strings (`../data/provenance.md`, spike).
- Thresholds for "acceptable" are not set; they require a pilot.

### Tier 3: scoring consistency
- **Determinism**: same observations and `as_of` ⇒ identical output, repeated.
- **Monotonicity**: adding an active week never lowers `active_weeks_last_4`; per-dimension rules do not invert with more evidence.
- **Missing-data behaviour**: absent day ⇒ `None`, never 0; stale ⇒ stated, not silently used; `measured_zero` ≠ missing; no-provider ⇒ `no_evidence`.
- **Golden fixtures**: hand-written inputs with expected outputs for each rule branch (up/down/flat, each missing-data branch, partial calendar). Fixtures are synthetic and labelled as such; they test logic, not real-world accuracy.
- **Version comparability**: snapshots compare only under the same `evidence_version` (`compare()` in `assessment.ts`).

### Tier 4: predictive performance (RQ1 only)
- Scope: forecast active weeks (0–4) in the next 4 weeks from 12 weeks of daily counts (`../ml/experiment-protocol.md` §B1). Nothing else is evaluated for prediction.
- Gate (ADR 0005, owner decision 2026-10-22): on the opened user-disjoint test set, skill = 1 − MAE_model / MAE_persistence; promote only if skill ≥ 0.10 **and** the lower bound of the user-level 95% bootstrap CI of skill > 0. Otherwise rules only.
- Baselines first, temporal and group-aware split with a 28-day gap, test set opened once, REFORMS checklist (protocol §B3).
- Current result: none. No consented export exists; the outcome is "inconclusive — rules only" (ADR 0005). A pass would support only "forecasts next-4-week GitHub activity for this population", not any placement claim.
- Needs RQ1 approval, the consent/recruitment route (decision 6) and a pilot first.

### Tier 5: recommendation quality
- **Rule traceability**: every recommendation records rule id and the evidence field; a test fails if one lacks either.
- **Expert review**: a panel (size, selection and rubric to be defined before review) rates each rule's text for accuracy, actionability and harm. Report inter-rater agreement (statistic chosen before review) alongside any pass/fail; do not report agreement as a quality score on its own.
- Rule copy today (`priorities()`) has not been expert-reviewed.

### Tier 6: real-world usefulness
- Whether students change what they practise, understand the coverage and caveats, and find the nudges fair. Requires a consented study design (decision 6), pre-registered outcomes and a power calculation. No claim about job outcomes.
- Error costs to watch (`../ml/target.md` §5): false reassurance, discouragement, penalising private or off-platform work.

### Minimum evidence before anything may be called "validated"
A component may be called validated only when all hold, stated for that component and that claim only:
1. The claim is written down before data is inspected, and does not mention placement or hiring.
2. The relevant tier's pre-registered criteria are met on data not used to design or tune it.
3. The sample size was set by a power calculation (not guessed), real consented `observed` data only (no synthetic).
4. Uncertainty is reported (user-level CIs or inter-rater agreement) and failures are analysed (worst-error review, protocol §B3).
5. Reproducibility record exists: data hash, code commit, versions, seeds.
6. Rollback path exists for anything promoted (`ml/bundle.py`, ADR 0005).

Until then: "proposed", "heuristic" or "unvalidated". Tiers 1 and 3 can only validate software behaviour and rule consistency.

## 7. Open decisions and unverified items (quoted)

Open decisions:
- `../ml/target.md` §6: "GitHub: public username only vs OAuth device flow (§19 #3). Recommendation: public-only first, OAuth later."
- `../ml/target.md` §6: "LeetCode: keep the integration only as labelled aggregates, or use manual entry. ToS not verified (§19 #4)."
- `../ml/target.md` §6: "Whether any placement outcomes will ever be collected, from whom, with what consent (§19 #14, #13)."
- `../ml/target.md` §6: "Consent and recruitment route for RQ1 (protocol §B6)."
- ADR 0005 Open items: "Owner approval of RQ1, baselines and split design." / "Recruitment and consent route." / "Retire the legacy RF score fully (API field and demo path)."
- `domain-model.md` §9: "Whether `cgpa` is stored at all (§19#5) and the backup retention window (§7) are open."
- `../ml/target.md` status: "proposed, needs human sign-off".
- Decided 2026-10-24: see §0 (decisions 1-7). Still open: IdP vendor, region, publisher string.

Unverified items:
- `../ml/experiment-protocol.md` §B4: "Window limit", "Timezone", "Private contributions", "ToS / API terms" are listed as "Still unverified".
- `../research/github-calendar-spike.md`: "Status of the 2026-10-22 re-run: not run."; "Hidden-private-contributions behavior for a third-party user: unverified."
- `../data/provenance.md`: "Unverified: GraphQL error `type` strings (taken from GitHub docs, not observed), which timezone GitHub uses to assign a contribution to a day, and private-contribution handling for other users' profiles." and "No live-network test against GitHub or LeetCode was run".
- `../data/provenance.md`: LeetCode "terms unverified".
- `../ml/experiment-protocol.md` §B2: "at least a few hundred users … is a placeholder, **unverified**, to be replaced by a power calculation."
- `domain-model.md` §9: "`draft-schema.sql` has not been run."
- Found while writing this spec, not in prior docs: `leetcode_solved_all` is not emitted by the backend (defect, fix scheduled in Phase 3.1); the `rows[0]` provenance choice in `_build_evidence`; `audit-report.md` figures not re-read.
