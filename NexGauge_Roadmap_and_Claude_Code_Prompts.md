# NexGauge: Complete Roadmap and Claude Code Prompts

Snapshot inspected: `PIS-main_1ceadd.zip` (2026-10-24). Checks were run on a Linux scratch copy (Python 3.12, PostgreSQL 16, Node 22). CI is configured for Python 3.11 and Postgres 15, so this is not the same environment.

---

## A. Executive summary

**What exists**
- A tested, security-conscious backend: `users`/`profiles`, integrations, sync runs, provenance-aware observations (with CHECK constraints), immutable assessment snapshots, privacy export/delete/audit, and a model-bundle registry.
- A desktop client with 7 screens and a design system, auth and session code, and mock-mode tests.
- Terraform for ECS Fargate + RDS, a release script, and docs and ADRs.

**What does not exist**
- No real user can receive an assessment. `POST /api/v1/assessments` always stores `insufficient_evidence`.
- No server-side dimension or recommendation logic. The only rules are in the client's `priorities()`.
- The product cannot start in staging/production as shipped. The API refuses to boot without a model bundle, and models are excluded from git and the image.
- Nothing has run against a live IdP, a real provider, a packaged desktop, Docker or AWS.
- All seven owner decisions in the intelligence spec are still open.

**What NexGauge needs**
1. Fix startup, container and CORS blockers.
2. Record decisions.
3. Harden the data path.
4. Build the server-side deterministic assessment.
5. Add recommendations and progress.
6. Wire the desktop to them.
7. Deploy a staging stack under your approval.
8. Run a consented pilot.
9. Keep ML as a gated side track.

---

## B. Verified repository state

| Check | Result |
|---|---|
| `ruff check .`, `ruff format --check .` (95 files), `mypy` (26 files) | Pass |
| `pytest --cov=app --cov=services --cov=ml --cov=ingest` | 294 passed, coverage 82.60% (floor 79%) |
| Desktop `npm ci`, `typecheck`, `lint`, `format`, `test`, `build` | Pass; 8 files, 55 tests |
| Docker, `tauri build`, installer, live IdP, real GitHub/LeetCode, AWS, remote CI | **Not run** |

**Findings A–J against the code**

| | Verdict | Evidence |
|---|---|---|
| A | Confirmed | `app/routers/v1.py:275–277` hard-codes `'insufficient_evidence'` |
| B | **Confirmed defect.** The spec calls it "not verified", but the code does not emit it | `leetcode_solved_all` appears only in `apps/desktop/src/api/mock.ts`, `lib/assessment.ts` and `screens/Overview.tsx`; the adapter and validators emit only `_easy`, `_medium`, `_hard` |
| C | Confirmed | `docs/architecture/intelligence-spec.md` §0: draft, not implemented, all 7 decisions OPEN |
| D | Confirmed | Spec §3 defines per-dimension states and no composite |
| E | Confirmed | `docs/ml/dataset-card.md`, `ml/labels.py` (formula + noise); the model is reachable only from the local boot (`entrypoint.sh`) |
| F | Confirmed | `docs/ml/forecast-report.md`: never run on real data; `ml/forecast/run.py` does not yet evaluate the 0.10 promotion threshold |
| G | Confirmed | Migrations 000–008, 31 routes (`docs/architecture/api-surface.md`, drift-tested), `services/sync.py` 96% covered, `services/privacy.py`, `ml/bundle.py` |
| H | Partly resolved by reading code, still unrun | See below |
| I | Confirmed | `deploy/aws/main.tf` (417 lines); ADR 0004 says never validated or applied; `docs/ops/runbook.md` marks apply steps `[todo]` |
| J | Confirmed | 7 screens in `apps/desktop/src/screens/`, 14 components, 9 screenshots in `docs/design/screens/` |

**Code-level blockers beyond H**
- `app/main.py` lifespan calls `load_active()` and fails startup without an active bundle. `/health/ready` also returns 503 without one.
- `.gitignore` and `.dockerignore` exclude `models/bundles/` and `models/staging/`. `entrypoint.sh` skips training in staging/production. So the image has no model and the API cannot start there (from reading the code, not from a run).
- The real-user path never uses the model, so this requirement is unnecessary for real users.
- `grep CORSMiddleware app` returns nothing. Whether WebView2 blocks the app's cross-origin `fetch` is unrun. The Tauri `connect-src` is `https:` plus `localhost:8000`.
- `Dockerfile` (python:3.11-slim) installs `requirements-dev.txt` and has no `USER`.
- Rate limiting is per process (`app/auth.py:37`).
- `_build_evidence` sets a block's provenance from an arbitrary row (no `ORDER BY`) and does not read `value_state`. The spec flags this itself.
- `docs/ops/release/clean-machine-matrix.md` says "NOT YET RUN".

**Reported history vs evidence**
- `tauri.conf.json`: `productName` NexGauge, `version` 0.1.0, `identifier` `app.pis.desktop`, publisher "PIS Project", copyright "Abhiix0". Verified by reading.
- A built `NexGauge_0.1.0_x64-setup.exe` is reported but unverified here, and no clean install was recorded.

---

## C. Full phased roadmap

### Phase 0: Rebrand residuals (outstanding items only)
- **State:** strings, CI artifact name and copyright are done. The icon (old "P"), the publisher string and the clean install are not.
- **Work:** publisher string, icon swap when you supply an asset, installer filename check in `install-guide.md`.
- **Files:** `apps/desktop/src-tauri/tauri.conf.json`, `icons/*`, `docs/ops/release/install-guide.md`.
- **Depends on:** your inputs. Run just before Phase 9.
- **Acceptance:** no "PIS Project" publisher unless you choose to keep it; icon replaced or logged as a known limitation.
- **Out of scope:** renaming the identifier or package names.

### Phase 1: Foundation and stability
- **State:** backend checks are green. Production startup, CORS, container and Windows verification are unresolved.
- **Work:** decouple startup and readiness from the model in staging/production; add a CORS allowlist; harden the Dockerfile; run the Docker/Tauri/desktop-to-API checks and update the baseline doc with real results.
- **Files:** `app/main.py`, `config.py`, `Dockerfile`, `docker-compose.yml`, `entrypoint.sh`, `docs/ops/runbook.md`, `docs/architecture/baseline-2026-10.md`.
- **Deliverables:** staging-mode startup test, CORS tests, verified installer filename.
- **Acceptance:** S-01..S-04 each have a verdict from a run; the baseline doc lists only executed results.
- **Risks:** needs Docker and a Rust/Windows machine. **Out of scope:** AWS and UI changes.

### Phase 2: Decisions and contracts
- **State:** spec, ADR 0005 and target docs exist but are "proposed". Nothing is approved.
- **Work:** record your answers and reconcile doc drift. No new specification (`intelligence-spec.md` is the contract).
- **Files:** `intelligence-spec.md`, `docs/ml/target.md`, ADR 0005, ADR 0004 open items, `current-state.md`.
- **Acceptance:** every decision is Approved with a date or still OPEN.
- **Out of scope:** any code.

### Phase 3: Data workflows and security
- **State:** implemented and mock-tested; live paths unverified; one contract defect (B) plus the spec's evidence inconsistencies.
- **Work:** evidence-contract fix and determinism; isolation tests for every user route; first-login user creation, validation, sync edge cases and deletion; tests for lifespan and admin paths (53% and 50% covered); secret-pattern scan; live IdP/GitHub/optional LeetCode verification (separate prompt).
- **Files:** `app/routers/v1.py`, `app/auth.py`, `services/sync.py`, `services/privacy.py`, `ingest/*`, `tests/*`, `docs/security/auth-architecture.md`.
- **Depends on:** Phase 1, Phase 2 (IdP choice).
- **Acceptance:** no cross-user access under test; live sign-in works or the gap is recorded.
- **Risks:** IdP configuration (loopback redirect on any port, custom role claim). **Out of scope:** new endpoints.

### Phase 4: Real-user deterministic assessment
- **State:** missing; only evidence snapshots exist.
- **Work:** a pure-function rules engine over persisted evidence; dimension states `no_evidence`, `stale`, `partial`, `sufficient`, `source_failed`; server-side staleness; `rules-v1` and `evidence-v2` versioning; coverage and caveat text; immutable storage; a migration only if migration 007's CHECK on `assessment_type` requires it.
- **Files:** new `services/assessment.py`, `app/routers/v1.py`, `features/as_of.py` (reuse), `sql/migrations/009_*.sql` (conditional), `docs/architecture/api-v1.md`.
- **Depends on:** Phases 2–3.
- **Acceptance:** golden-fixture tests; no composite number; every output has provenance, timestamp, rule id and a limitations statement.
- **Out of scope:** ML, a composite score, recommendations.

### Phase 5: Recommendations and progress
- **State:** 7 client-side rules (`priorities()`) and client-side snapshot comparison.
- **Work:** move recommendations server-side as traceable rules (id, reason, evidence refs, rule id, order); server-side comparison with a version-compatibility disclosure; drop the CGPA-missing nag if CGPA is confirmed not to be evidence.
- **Files:** `services/assessment.py` or sibling, `app/routers/v1.py`, `docs/architecture/api-surface.md`, tests.
- **Depends on:** Phase 4.
- **Acceptance:** determinism, empty/partial states, no causal claims.
- **Out of scope:** ML ranking, LLM text.

### Phase 6: Desktop MVP
- **State:** screens, auth session, mock mode and design system exist; they consume the old client-side rules.
- **Work:** wire the UI to the server contract and remove duplicate client rules; first-run onboarding (profile, connect, sync, assess); sign-out, profile edit, privacy controls; offline/stale/partial/error states; accessibility, DPI and minimum-window pass; update the mock; regenerate screenshots.
- **Files:** `apps/desktop/src/{screens,lib,api,components}`, `docs/design/*`.
- **Depends on:** Phases 4–5.
- **Acceptance:** no demo data shown as real data; a vitest state matrix per screen.
- **Out of scope:** visual redesign or new screens beyond onboarding.

### Phase 7: Cloud deployment and operations
> **Free-host comparison done 2026-10-24: `docs/ops/free-hosting.md`** (recommended compromise: Render free web service + Neon free Postgres; unverified until the owner creates accounts).
> **Budget constraint (decision 10, $0):** before 7.2, compare free hosts for the FastAPI backend, PostgreSQL and the desktop's API connection. Criteria: sleep/cold starts, DB persistence and storage limits, quotas, region, network limits, runs without your computer. Existing Terraform stays unless an approved change is needed. Nothing is marked complete until the chosen setup is verified at $0, with no spend to verify. If no free combination fits, propose the best zero-cost compromise; never add paid infrastructure silently.

- **State:** Terraform written but never validated; release script unverified.
- **Local preparation (no AWS):** `terraform fmt/validate` (backend-less), review `main.tf`, document cost assumptions, dry-run `release.sh`, restore drill on local Postgres, logging check, runbook fixes.
- **Authorized deployment (your approval; AWS only if provably $0, else the chosen free host):** staging plan/apply, secrets, migrate task, smoke, restore and rollback drills, teardown.
- **Depends on:** Phase 1; Phase 2 (region, budget, IdP).
- **Acceptance:** a staging stack serves `/health/ready` over HTTPS; a restore and a rollback were each rehearsed.
- **Risks:** cost (ALB, NAT, RDS). **Out of scope:** production, Multi-AZ, a platform change.

### Phase 8: ML research (gated)
- **State:** smoke-test experiment, forecast pipeline (tests pass, results empty), bundle registry.
- **Work now:** quarantine the legacy RF from the real-user surface; add the pre-registered promotion check to `ml/forecast/run.py`; model/dataset cards.
- **Work later:** run the forecast on consented real data only.
- **Acceptance:** no result is recorded without a data hash and the ADR gate applied; no real data means the gate stays "inconclusive".
- **Out of scope:** any model in the real-user assessment.

### Phase 9: Release readiness and pilot
- **Work:** tighten CSP to the API origin; CI release dry-run; user documentation and in-app limitations statement; dependency and secret audit; privacy review against `docs/data/privacy-and-retention.md`; clean-machine matrix (done by you); small consented pilot with triage.
- **Depends on:** Phases 0, 6, 7.
- **Acceptance:** see section F.
- **Out of scope:** publishing without your authorization.

---

## D. Dependency map

**Critical path:** P1.1 → P2 → P3.1 → P4 → P5 → P6.1 → P6.2 → P7.2 → P9.

**Parallel work**
- P1.2 (verification) runs alongside P2/P3.1 on a Docker/Windows machine.
- P3.2 starts once the IdP is chosen.
- P7.1 starts after P1.1.
- P8.1 runs any time after P4.
- P0 and P9.1 prep run alongside P6.

**Owner decisions** (recommended defaults are not approvals; you set each in the Phase 2 prompt)

| # | Decision | Recommended default and consequence |
|---|---|---|
| 1 | Path B wording (no placement claim) | **Approved 2026-10-24.** Closes outcome prediction until real labels exist |
| 2 | Composite score? | **Approved 2026-10-24.** None for MVP; dimension-level states only |
| 3 | CGPA | **Approved 2026-10-24.** Optional, self-reported context only; excluded from evidence and recommendations |
| 4 | LeetCode | **Approved 2026-10-24.** Disabled until the owner reads the ToS; manual entry later if disallowed |
| 5 | GitHub scope | **Approved 2026-10-24.** Public username only; calendar keeps its two flags; OAuth later |
| 6 | Research consent | **Approved 2026-10-24.** Separate opt-in; forecasting research deferred |
| 7 | v1 dimensions | **Approved 2026-10-24.** D1 activity, D2 project footprint, D3 LeetCode (flag-gated, off), D4 CGPA context only |
| 8 | IdP | OPEN: evaluate Clerk against loopback PKCE on any port, `offline_access` and a role claim (Phase 3.2 tests this); otherwise any compatible OIDC provider. Never configure an unverified provider as verified |
| 9 | Host region | OPEN. Was `ap-south-1`; now depends on the free host chosen under decision 10 |
| 10 | Budget and sizing | **Approved 2026-10-24: $0/month, free services only.** No paid AWS resource even temporarily (ALB, NAT, RDS, paid compute). AWS is used only if the whole setup stays at $0; otherwise a free alternative host is chosen. Verify each free tier's current limits, duration and billing behaviour before recommending it; no promotional credits counted as free |
| 11 | Publisher string | OPEN: owner supplies a name or handle (not an invented organization); `PIS Project` retained meanwhile |
| 12 | Signing and updates | **Approved 2026-10-24.** Unsigned pilot (SmartScreen warning documented); manual GitHub Releases |

---

## E. Claude Code prompts

Paste the **STANDARD RULES** block at the top of every prompt below.

```
STANDARD RULES (apply to this task):
- Run `git status --short` first; preserve unrelated changes; never assume a clean tree. Read each file before editing; reuse existing helpers and conventions (CLAUDE.md, CONTRIBUTING.md).
- Do only this task's scope. No refactors, new features, or UI redesign beyond it. Do not rename internal identifiers (app.pis.desktop, pis-export-v1, pis_* names/roles, PIS_* CI vars, npm/Cargo package names). Never edit an applied migration; schema changes are new numbered files in sql/migrations/.
- Wording: "preparation assessment" / "evidence". Never claim to predict hiring or placement; never treat GitHub activity as proof of ability; never show demo/synthetic data as a real user's.
- Databases: use only a throwaway scratch database (TEST_ADMIN_DATABASE_URL role with CREATEDB). Never reset, drop, or migrate an existing database.
- Validation: run targeted tests while working; run the full checks once at the end: `ruff check .`, `ruff format --check .`, `mypy`, `pytest --cov=app --cov=services --cov=ml --cov=ingest` (floor 79%); in apps/desktop (only if touched): `npm run typecheck`, `lint`, `format`, `test`, `build`. Reference baseline from an independent run on 2026-10-24: 294 pytest passed (82.6% coverage), 55 vitest passed. Report pre-existing failures separately from regressions.
- Never commit, push, publish, deploy, or provision cloud resources unless this prompt contains an explicit AUTHORIZED line. If a decision, credential, consent, or environment is missing, STOP and report it. Never invent results; mark anything you could not run "not run".
- Final report: files changed, each command with its real result, acceptance checklist pass/fail, unresolved issues.
```

### Phase 0: Branding residuals (run just before Phase 9)

```
[STANDARD RULES]

Task: Phase 0 residual branding. INPUTS (fill; blank = leave unchanged and report): PUBLISHER="<your name/handle>"; ICON_SOURCE="<path to a 1024px PNG or SVG you supply, or empty>".
Scope: apps/desktop/src-tauri/tauri.conf.json, apps/desktop/src-tauri/icons/*, docs/ops/release/install-guide.md.
1. bundle.publisher -> PUBLISHER only if provided. Keep identifier "app.pis.desktop", version, copyright.
2. If ICON_SOURCE is provided and exists: regenerate the icon set with `npx tauri icon <ICON_SOURCE>` (run in apps/desktop), keep the file names tauri.conf.json already lists. If empty: change nothing and report "old P icon retained (known limitation)". Do not create artwork.
3. Confirm the installer filename from a real `npx tauri build` (if cargo is available) and make install-guide.md match it exactly; otherwise mark it unconfirmed.
Validate: JSON parses; `npm run build`; tauri build if available.
Acceptance: publisher/icon changed only as supplied; install-guide filename equals the built one or is marked unconfirmed.
```

### Phase 1.1: Startup, container and CORS

```
[STANDARD RULES]

Task: Phase 1.1: make the backend startable in staging/production and the container reproducible.
Scope: app/main.py, config.py, .env.example, Dockerfile, docker-compose.yml, entrypoint.sh, .dockerignore, tests/test_ops.py, tests/test_config.py, docs/ops/runbook.md.
Evidence: app/main.py lifespan fails without an active model bundle and /health/ready returns 503 without one; models/bundles is in .gitignore and .dockerignore; entrypoint.sh skips training in staging/production. Real-user assessments never use the model.
1. In staging/production: lifespan and /health/ready require only config.validate(), DB reachable, and migrations applied. The model must NOT be required; /health/detailed reports model "none". Local/test behavior unchanged (still fails fast without a usable model). Admin model routes unchanged. Add tests for both modes.
2. CORS: add CORSMiddleware driven by env CORS_ALLOWED_ORIGINS (comma list; default empty = no cross-origin access). In staging/production validate() rejects "*". Add the var to .env.example with the desktop origins to set: http://tauri.localhost, tauri://localhost, http://localhost:1420 (which one WebView2 actually sends is verified in 1.2). Tests: allowed origin gets Access-Control-Allow-Origin and an Authorization-capable preflight; unknown origin gets none; the error envelope is unchanged.
3. Dockerfile: build arg INSTALL_DEV (default 0) so the runtime image installs requirements.txt only; docker-compose.yml passes INSTALL_DEV=1 for local; run as a non-root user; create models/ in the image; fix the misplaced chmod. Keep python:3.11-slim and entrypoint behavior.
4. Update the runbook "Model bundles" paragraph.
Validate: targeted tests first, then the full checks; if Docker is available `docker build -t nexgauge-api:p1 .` and a staging-mode run with dummy non-placeholder AUTH_* values and a scratch DB container expecting GET /health/ready = 200 with no model; otherwise report "docker not run".
Acceptance: staging-mode readiness tests pass without a bundle; local mode still requires one; CORS tests pass; no secrets in diffs.
```

### Phase 1.2: Environment verification (needs Docker; Rust on Windows)

```
[STANDARD RULES]

Task: Phase 1.2: verify the unrun items and record only real results. Needs Docker, and Rust/WebView2 on Windows. Files you may edit: docs/architecture/baseline-2026-10.md, docs/architecture/current-state.md (header/branch/count drift only), docs/ops/release/install-guide.md. No code changes; if a step is blocked by a bug, report it.
Use a unique compose project name `nx_p1`; only ever run `down -v` for that project; never `make down-clean`.
Run and record: (1) `docker compose -p nx_p1 up --build`, /health, /health/ready, /health/detailed, 401 on /api/v1/me; pytest inside the api container; boot chain features.compute -> ml.train -> ml.bundle bootstrap -> ml.predict. (2) the runtime image in staging mode (from 1.1). (3) Python 3.11 pytest if available. (4) apps/desktop: npm ci, npm run build, `npx tauri build`: exact installer filename and SHA-256. (5) Run the packaged app (or `npx tauri dev`) against the local API with CORS_ALLOWED_ORIGINS set: record the Origin header actually sent (API log or devtools) and whether requests succeed; mock mode only for UI states. (6) tests/test_sync.py::test_unexpected_adapter_crash_still_closes_the_run x3.
Verdicts for S-01 CORS from webview, S-02 production image without models, S-03 live OIDC (not run unless IdP exists), S-04 test_sync flakiness. Replace "definitions missing" in the baseline doc with these definitions and verdicts; fix the stale lines (branch name, test counts) in current-state/audit docs only where your run proves them wrong.
Acceptance: every row is Pass/Fail/Not run with evidence; installer filename matches install-guide.md or is flagged.
```

### Phase 2: Decision record and doc reconciliation

```
[STANDARD RULES]

Task: Phase 2: record owner decisions and reconcile docs. Docs only; no code. Do not create new specification files: `docs/architecture/intelligence-spec.md` is the contract.
OWNER DECISIONS (I edit these; a blank or "OPEN" line stays OPEN; you must not fill it in):
1 Path B wording approved: <yes/no/OPEN>   2 Composite score: <none for MVP / yes / OPEN>   3 CGPA: <optional context only / drop / OPEN>   4 LeetCode: <off until ToS read / manual entry / OPEN>   5 GitHub scope: <public username only / OAuth later / OPEN>   6 Research consent: <separate opt-in, defer / OPEN>   7 v1 dimensions: <D1-D3 + D4 context / OPEN>   8 IdP vendor: <name / OPEN>   9 AWS region: <value / OPEN>   10 Monthly budget USD + sizing: <value / OPEN>   11 Signing/updates: <unsigned pilot, manual releases / OPEN>
Edit: intelligence-spec.md section 0 status table and any dependent sections; docs/ml/target.md section 6; ADR 0005 Status; ADR 0004 open items (items 1-4); docs/data/provenance.md only if a decision changes it; docs/product/PIS_PRD.md section 19: one-line pointers only, no rewrites.
Also fix: the provenance class naming mismatch (target.md vs domain-model.md: follow domain-model.md); the spec's statement about leetcode_solved_all (code does not emit it; backend fix is scheduled in Phase 3.1); model-lifecycle.md stale "insights/" mention; unused sqlalchemy note in current-state.md if still true (verify first).
Do not touch docs/history/*, migrations, or code.
Validate: relative-link check over changed .md files (throwaway script, not committed).
Acceptance: each decision shows Approved <date> or OPEN; no number or threshold in docs is presented as validated.
```

### Phase 3.1: Data workflows and security hardening (offline)

```
[STANDARD RULES]

Task: Phase 3.1: close the evidence contract gap and prove isolation and lifecycle behavior. No new routes.
Scope: app/routers/v1.py (_build_evidence), app/auth.py, services/sync.py, services/privacy.py, tests/test_api_v1.py, tests/test_sync.py, tests/test_auth.py, tests/test_ops.py, docs/data/data-dictionary.md, docs/security/hardening.md.
1. _build_evidence: (a) when the latest LeetCode run has all of leetcode_solved_easy/_medium/_hard, add values["leetcode_solved_all"] = their sum, flagged derived; if any is missing, omit (missing is not zero). (b) select value_state; add ORDER BY so the block is deterministic; block provenance = the weakest provenance among its rows (read docs/data/data-dictionary.md for the rule). (c) bump EVIDENCE_VERSION to "evidence-v2" and keep older stored snapshots readable (check the client comparison logic in apps/desktop/src/lib/assessment.ts and report, don't edit, client changes).
2. Verify by reading, then test what is missing: first-login user/profile creation from a JWT sub; profile validation (cgpa 0-10, graduation_year); cross-user isolation on EVERY /api/v1 route (parametrize from app.routes; user A cannot read or alter user B); sync (one running per connection, cooldown, disconnect with and without delete_data, provider failure writes nothing); deletion irreversibility, account lock and audit event; export contains no tokens or other users' data; rate limit on expensive routes.
3. Add tests that raise coverage of app/main.py lifespan and app/routers/admin.py operator paths (currently 53% and 50%) using the existing minimal-bundle fixture.
4. Scan tracked files for secret-like strings and report file:line only, never the value.
5. Document the per-process rate limit as an accepted pilot limitation in docs/security/hardening.md.
Fix only confirmed defects, minimally. Acceptance: new tests fail before the fixes where a defect existed and pass after; full checks green; coverage >= 82%.
```

### Phase 3.2: Live IdP and provider verification (needs your credentials)

```
[STANDARD RULES]

Task: Phase 3.2: live verification against a dev IdP tenant and real providers. PRECONDITIONS (stop and report if missing): an IdP dev tenant with a native/public client (authorization code + PKCE, loopback redirect on any port, offline_access), issuer/audience/JWKS URL, a custom role claim mapped to AUTH_ROLE_CLAIM (default pis_roles), my own GitHub account, GITHUB_TOKEN. Credentials come only from my shell env; never print, log, write or commit them.
Do: (1) run the API locally with real AUTH_* against a scratch DB; (2) sign in through apps/desktop (tauri dev) and confirm GET /api/v1/me, token refresh, and POST /auth/logout revoking older tokens; (3) confirm an ordinary user gets 403 on /admin/* and a role-bearing user is allowed; (4) connect my GitHub username and run a real sync with GITHUB_CALENDAR_ENABLED per approved decision 5; inspect source_observations for provenance, event_at precision, and quality results; (5) re-run experiments/spikes/github_calendar_spike.py rows still unverified in docs/research/github-calendar-spike.md; (6) LeetCode only if decision 4 allows it, else skip and say so.
Update: docs/security/auth-architecture.md with the exact IdP settings that worked; the spike doc rows (verified or still unverified); the baseline doc S-03 verdict. Fix confirmed defects minimally in app/auth.py or src/auth/*; otherwise report.
Acceptance: sign-in, refresh, logout, role check and one real sync each have an observed result or "not run: reason".
```

### Phase 4: Deterministic assessment

```
[STANDARD RULES]

Task: Phase 4: implement the server-side deterministic preparation assessment (rules-v1) per docs/architecture/intelligence-spec.md and approved decisions in section 0. If decision 2 is not "no composite", STOP and report.
Scope: new services/assessment.py (pure functions), app/routers/v1.py (create_assessment, get_assessment, evidence route), features/as_of.py (reuse activity_trend), sql/migrations (new file ONLY if the assessments table or its assessment_type CHECK in migration 007 cannot hold the result; forward-only and backward compatible; scratch DB only), docs/architecture/api-v1.md, docs/architecture/api-surface.md if routes change, tests.
Build:
1. compute_assessment(evidence, now) -> dict with one object per approved dimension (D1 activity consistency, D2 project footprint, D3 LeetCode volume if enabled, D4 as context) containing: dimension, evidence_state (no_evidence | stale | partial | sufficient | source_failed per spec section 3), values[] (name, value, provenance, value_state, event_at precision, collected/synced timestamps, sync_run_id), rule {id, text}, coverage line, caveats[] from the spec's "cannot establish" text, plus assessment_version "rules-v1" and evidence_version.
2. Semantics: absent is never zero; measured_zero shown as "0, reported by the provider"; staleness computed server-side from synced_at with the proposed 7-day window in one named constant labelled "proposed, unvalidated"; calendar trend requires the full 12 weeks else direction None.
3. create_assessment stores the result immutably. If no provider has any evidence, keep assessment_type 'insufficient_evidence'. NO composite or numeric readiness score. Keep existing response fields additive; the legacy readiness_score stays null for real users.
4. Tests: golden fixtures for each state (not connected, never synced, failed sync, stale, partial calendar, measured zero, full evidence); determinism (same input same output); immutability; cross-user isolation; assessment JSON contains no forbidden phrases (placement probability, chance of getting placed, predicts); synthetic provenance rejected for real users.
5. Mark the spec: "implemented as rules-v1, not validated".
Validate: targeted tests then full checks. Acceptance: all dimensions carry provenance, timestamps, rule id, coverage and caveats; no score number anywhere; migrations (if any) apply on a scratch DB from empty and from the previous head.
```

### Phase 5: Recommendations and progress

```
[STANDARD RULES]

Task: Phase 5: server-side traceable recommendations and snapshot comparison.
Scope: services/assessment.py (or a sibling module), app/routers/v1.py, docs/architecture/api-surface.md + api-v1.md, tests.
1. Port the rule set from apps/desktop/src/lib/assessment.ts::priorities() to the server as deterministic rules. Each recommendation: id, rule_id, priority order, action text, reason, evidence_refs (dimension, value name, sync_run_id), and a limitation line. Rules cover: nothing connected; provider stale; failed sync; zero public repos; calendar partial; activity trend down; LeetCode total zero (only if enabled). Apply approved decision 3: drop the CGPA-missing nag if CGPA is context only. Every number/threshold in the rules is a named constant labelled "proposed, unvalidated".
2. Store the recommendations inside the immutable assessment result (rules version recorded).
3. Add GET /api/v1/assessments/{id}/compare/{other_id} (caller-owned only) returning per-dimension deltas and a disclosure when evidence_version/assessment_version/coverage differ (non-comparable fields are marked, not diffed). Add the route row to api-surface.md (a test enforces it).
4. Wording: no claim that following a recommendation improves employment outcomes.
5. Tests: determinism; empty/partial/stale evidence; ordering stability; comparison across versions; cross-user 404/403; no forbidden phrases.
Validate: targeted then full checks. Acceptance: every recommendation is traceable to an evidence ref and a rule id; comparison never diffs incompatible fields silently.
```

### Phase 6.1: Desktop workflow wiring

```
[STANDARD RULES]

Task: Phase 6.1: connect the existing desktop screens to the real server contract and complete the first-run flow. Reuse apps/desktop/src/components and docs/design/design-system.md; no redesign, no new dependencies.
Scope: apps/desktop/src/{App.tsx,api,lib,screens,auth}, docs/design/desktop.md.
1. Types/client: update api types and mock.ts to the real Phase 4/5 contract (dimensions, evidence_state, recommendations, compare). The mock must match server field names and states (including stale, partial, source_failed, insufficient_evidence).
2. Overview, Assessment, Plan, History: render dimension cards (state badge, values with provenance and time, rule text, coverage, caveats), recommendations with their evidence, and comparison from the server. Delete the duplicated client-side priorities()/comparison rules once replaced; keep display helpers only.
3. First run: sign in -> profile -> connect integration -> sync with status -> first assessment, with a resume point if the user quits midway. Sign-out; profile edit; privacy export/delete flows verified against the real routes.
4. States for every screen: loading, empty, partial, stale, offline (API unreachable shows an error, never stale data as current), error with request_id.
5. Demo/mock content appears only when VITE_MOCK_API is on and is visibly labelled; production builds must not include it.
6. vitest: state matrix per screen, onboarding flow, sign-out, no-demo-in-prod check.
Validate: npm run typecheck, lint, format, test, build; backend untouched. Acceptance: with the mock off every screen works only through real API calls; a state matrix test covers each state; no client-side rule produces a recommendation.
```

### Phase 6.2: Usability, accessibility, responsiveness

```
[STANDARD RULES]

Task: Phase 6.2: quality pass on the existing desktop UI. No new features, dependencies, or redesign.
Scope: apps/desktop/src/{components,screens,styles}, docs/design/screens/*, docs/design/design-system.md (notes only).
1. Keyboard: full tab order, visible focus, Esc/Enter behavior in dialogs, no keyboard traps; semantic landmarks and headings; labels for every input; aria-live for status/errors; icon-only buttons named.
2. Contrast: check text/background pairs from the design tokens against WCAG AA; fix tokens only if a pair fails (record before/after).
3. Layout at 800x560 and 1100x760 and 100/125/150/200% scaling: no clipped controls or horizontal scroll; tables scroll inside their own container.
4. Copy review: every score-like wording follows the preparation-assessment rules; add an About/limitations panel (existing Card/Banner components) stating coverage and what the assessment cannot establish.
5. Regenerate the docs/design/screens/*.png with `npm run screenshots` (check the script first; mock mode only).
6. Tests with the existing testing-library setup (role/label queries, no new packages).
Validate: typecheck, lint, format, test, build. Acceptance: every interactive element reachable and named; AA pairs pass or fixed; screenshots regenerated; limitation text visible on Overview.
```

### Phase 7.1: Deployment preparation (local only, no AWS)

```
[STANDARD RULES]

Task: Phase 7.1: prepare and verify the deployment path locally. Do NOT run terraform plan/apply against AWS, push images, or call any AWS API. No AWS credentials are used.
Scope: deploy/aws/main.tf, deploy/aws/release.sh, .github/workflows/backend.yml, docs/ops/runbook.md, docs/data/privacy-and-retention.md (alignment only).
1. If terraform is installed: `terraform fmt -check`, `terraform init -backend=false`, `terraform validate`. Else report "not run". Fix validation errors minimally.
2. Review main.tf against the approved region/budget/IdP decisions: HTTPS listener and ACM variable, health path /health/ready, DB not public with sslmode=require in the secret instructions, secrets only via Secrets Manager, log retention, alarms present, desired count and sizing variables, Multi-AZ off by default for staging; list cost drivers (ALB, NAT, RDS) with the assumptions needed for the AWS Pricing Calculator; do not state prices.
3. release.sh: add a --dry-run mode that prints the steps and performs no build/push/AWS call; confirm it aborts on a dirty tree and on migration task failure by reading and by a shellcheck-style review (run shellcheck if available).
4. Backups: write and run on a scratch local Postgres a pg_dump/restore rehearsal; record the exact commands and the row-count check in the runbook as [done: local].
5. Logging: confirm request_id appears in server logs and errors; ensure no tokens/PII in logs (grep + test).
6. Update the runbook status legend honestly: only local rehearsals may be [done].
Validate: terraform commands above if available; full pytest only if app code changed. Acceptance: terraform validate result recorded; dry-run works; restore rehearsed locally; no AWS call was made.
```

### Phase 7.2: Staging deployment (explicit authorization required)

```
[STANDARD RULES]

AUTHORIZED: <write exactly "terraform apply for staging in <region>, budget USD 0" (or the chosen free host's equivalent) to authorize; any paid resource is refused regardless; if this line is absent or unchanged, perform only `terraform plan` output review and STOP before any apply, push, or billable resource.>

Task: Phase 7.2: deploy the staging stack with my AWS credentials supplied via the shell environment (never print or commit them).
Preconditions to verify first: Phase 7.1 recorded; ECR repo, state bucket/lock table, ACM certificate, VPC/subnets exist or are created per docs/ops/runbook.md section 2; IdP staging audience set.
Steps, stopping at the first failure: (1) terraform plan with staging tfvars (not committed) and summarize resources and cost drivers; (2) apply (authorized only); (3) put secrets via aws secretsmanager put-secret-value (values from env, never echoed); (4) deploy/aws/release.sh staging <region> <ecr-uri> (migration as a one-off task); (5) smoke test over HTTPS: /health, /health/ready, 401 on /api/v1/me, a real sign-in from the desktop against staging, one real sync and one assessment; (6) rehearse rollback to the previous image tag and verify; (7) restore drill: take a snapshot, restore to a new instance, run row-count checks, delete the restored instance; (8) confirm alarms and the budget alert exist; confirm the SNS subscription.
Record real results in docs/ops/runbook.md (change [todo]/[unverified] only for steps you ran). Report cost-relevant resources left running and the exact `terraform destroy` command; do NOT run destroy unless I authorize it.
Acceptance: staging serves HTTPS readiness; rollback and restore each have an observed result.
```

### Phase 8.1: ML quarantine and promotion check (no real data needed)

```
[STANDARD RULES]

Task: Phase 8.1: keep ML honest and ready for the data, without changing the real-user path.
Scope: ml/forecast/run.py, tests/test_forecast.py, app/routers/v1.py + apps/desktop/src (readiness_score exposure only), docs/ml/*, docs/architecture/decisions/0005-ml-direction.md.
1. Implement the ADR 0005 promotion check in ml/forecast/run.py: given a results JSON, compute pass/fail for skill >= 0.10 AND user-bootstrap CI lower bound > 0 on the opened user-disjoint test set, and write it into the report; unit-test pass, fail and "no test set opened" (inconclusive). Do not change split logic or thresholds.
2. Legacy RandomForest: confirm real-user responses carry readiness_score = null and no real-user code path imports ml.predict; add a test. In the UI, any display of the legacy score exists only in an explicitly labelled demo mode; if more is needed, report it rather than redesigning.
3. Add a model card for the bundle (docs/ml/model-lifecycle.md section) stating: trained on 8 synthetic rows, constructed labels, not validated, demo only. Update docs/ml/dataset-card.md only if facts changed.
4. Run `python -m ml.experiment` on a scratch copy and verify the output hash and recorded metadata match the committed baseline-synthetic report (report any mismatch; do not overwrite committed results).
5. Do NOT run ml/forecast/run.py on synthetic data as a result, and do not add any model to the assessment path.
Validate: targeted then full pytest. Acceptance: promotion check tested; no real-user path reaches the legacy model; model card present.
```

### Phase 8.2: Forecast experiment on consented data (gated)

```
[STANDARD RULES]

Task: Phase 8.2: run the pre-registered forecast evaluation ONLY if real consented data exists. Preconditions (stop and report "not run" if any is missing): research consent text approved (decision 6); users with research_consent_at set and provenance 'observed' in a real database export; MIN_USERS_PER_PARTITION replaced by a documented power calculation (do not keep the placeholder 20 as validated); I have supplied the export path: <path>.
Steps: (1) python -m ml.forecast.export to a git-ignored file; record counts, excluded share (bots, young accounts, private-only), and data hash; (2) run ml/forecast/run.py WITHOUT --open-test; review baselines and validation diagnostics; (3) only then run once with --open-test; apply the Phase 8.1 promotion check; (4) failure analysis of the worst 5% per slice; (5) fill docs/ml/forecast-report.md results rows with the real numbers and the REFORMS checklist; update ADR 0005 Outcome with pass / fail / inconclusive.
Rules: the test set is opened exactly once; no tuning after opening; no synthetic substitution; no claims beyond "forecasts next-4-week active weeks for this population"; a pass means a PROPOSAL for bundle promotion via ml/bundle.py, not an implementation.
Acceptance: every figure traces to a run on named data; otherwise "inconclusive" is recorded.
```

### Phase 9.1: Release engineering

```
[STANDARD RULES]

Task: Phase 9.1: release path preparation without publishing. Do NOT push tags, create GitHub releases, or change repository settings.
Scope: apps/desktop/src-tauri/tauri.conf.json (CSP only), .github/workflows/{desktop,release}.yml, docs/ops/release/*.md, README.md, docs/security/desktop-session.md.
1. Tighten CSP connect-src from https: plus localhost:8000 to the approved staging/production API origin(s) via a documented build-time setting if the existing build supports it; otherwise document the exact edit and keep dev origins out of release builds. Verify the desktop still reaches the API in tauri dev.
2. Review release.yml: tag must match app version (existing check), unsigned path works when no certificate secret, SHA256SUMS.txt and release.json content, draft-only release. Run `actionlint` if available; otherwise a careful read. Do not run the workflow.
3. Write the user documentation: README quick start for end users (no Python/Node/Docker), install-guide.md (SmartScreen note for unsigned builds, filename confirmed in 1.2/Phase 0), uninstall, sign-in help, what NexGauge measures and cannot establish, data handling and deletion (match docs/data/privacy-and-retention.md), known limitations (old icon if still true, unsigned, per-process rate limit). Update release-notes.md for 0.1.0 with only verified facts.
4. Upgrade behavior: check that identifier and keyring service are unchanged so an existing sign-in survives an upgrade; record how the installer behaves on upgrade only from an actual test, else mark unverified.
Validate: npm run build; docs link check. Acceptance: CSP no longer allows arbitrary https:; docs state only verified facts; no release created.
```

### Phase 9.2: Security/privacy review and pilot kit

```
[STANDARD RULES]

Task: Phase 9.2: final review and pilot preparation. No publishing; no production deploy.
1. Dependency audit: `pip-audit -r requirements.txt` and `npm audit --omit=dev` in apps/desktop (and `cargo audit` if installed); list findings with severity; fix only direct, low-risk updates and re-run tests; report the rest with reasoning.
2. Secret scan of tracked files and git history if .git exists (use gitleaks if installed; else a regex scan); report file:line/commit only, never values.
3. Privacy review against docs/data/privacy-and-retention.md and docs/security/*: verify by tests or reading that consent, export, deletion, audit events, retention statements and the data collected match what the code does; list mismatches and fix documentation or code minimally.
4. Pilot kit (docs/ops/release/pilot-plan.md, one file): voluntary participation, plain-language consent text separate from research consent, what is collected, how to withdraw/delete, support contact placeholder for me to fill, a feedback and defect-triage template with severity definitions, stop criteria, and the clean-machine matrix handoff (the matrix itself is filled by me on real machines; leave results blank).
5. Acceptance record: add to docs/architecture/baseline-2026-10.md a final table of Phase 1-9 checks with Pass/Fail/Not run and evidence.
Acceptance: no unresolved high/critical dependency or secret finding without an explicit owner decision; pilot kit exists; no claim in docs exceeds the evidence.
```

---

## F. Global definition of done

**MVP (all required)**
- A new user signs in through the real IdP, creates a profile, connects GitHub, syncs, and receives a server-computed assessment on the packaged desktop against a deployed staging backend.
- The assessment shows per-dimension evidence states, provenance, timestamps, rule text, coverage and caveats. It has no composite score and no placement or hiring claim.
- Recommendations are traceable rules with evidence refs. Comparison across snapshots discloses version differences.
- Offline, stale, partial and error states are tested; demo data never appears for real users.
- Export and deletion work end to end. Cross-user isolation is tested on every route.
- CI backend and desktop checks pass in remote CI. Coverage is at least 79%.
- Restore and rollback were each rehearsed on staging.
- The clean-machine matrix passes (install, launch, sign-in, upgrade, uninstall).
- A pilot with a handful of consenting users completed, and triage records no open critical defects.

**Required for a public release, in addition**
- Decision on code signing and the update channel.
- Dependency and secret audits resolved.
- A production stack, separate from staging, only after your explicit authorization.
- The final acceptance table in `baseline-2026-10.md` contains no "Not run" in a required row.

**Post-MVP, not required:** OAuth for private repos, manual-entry LeetCode, a composite score (only if validated), macOS/Linux builds, an auto-updater, a web app, multi-AZ.

**Conditional research track:** the forecast evaluation (Phase 8.2) and any model promotion require consented data and the ADR 0005 gate. "Inconclusive" is an acceptable outcome, and the product ships without it.

---

## G. Immediate execution order

1. Start with **STANDARD RULES + Phase 1.1**.
2. On a Docker/Windows machine, run **Phase 1.2**. In parallel, fill the decision block and run **Phase 2**, and begin IdP setup.
3. Run **Phase 3.1**, then **Phase 3.2** once the IdP exists.
4. Run **Phase 4**, then **Phase 5**.
5. Run **Phase 6.1**, then **Phase 6.2**.
6. Run **Phase 7.1** any time after 1.1. Run **Phase 7.2** only when you type the AUTHORIZED line.
7. Run **Phase 8.1** any time after Phase 4. Run **Phase 8.2** only if consented data exists.
8. Run **Phase 0**, then **Phase 9.1**, then you run the clean-machine matrix, then **Phase 9.2**, then the pilot.
