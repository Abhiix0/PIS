# PIS — Phased Implementation Plan

**Document type:** Engineering execution roadmap  
**Status:** Proposed; update as decisions are made  
**Version:** 1.0  
**Date:** 13 October 2026  
**Primary product:** PIS cloud-connected Windows desktop application  
**PRD:** `PIS_PRD.md`  
**Current repository:** `PIS`

> This plan turns the PIS PRD into an execution sequence. Work phase by phase, keep changes small, and do not begin the next phase until the current phase's exit gate is satisfied. Dates and effort estimates are intentionally omitted: the sequence depends on repository findings, data feasibility, and product decisions.

---

# 0. The North Star

PIS will be an installable Windows desktop application with a modern React interface and a cloud-hosted Python intelligence backend. Users should not need to install Python, Node.js, Docker, PostgreSQL, or configure a local server.

**Agreed direction**

- **Desktop:** Tauri 2 + React + TypeScript.
- **Cloud API:** FastAPI + Python.
- **System of record:** Managed PostgreSQL.
- **ML:** Python/scikit-learn initially; select models through evidence, not fashion.
- **First desktop target:** Windows x64.
- **Existing UI:** Streamlit remains available for local development until the new desktop client replaces its required workflows and passes acceptance tests.
- **Product positioning:** Personal preparation intelligence, unless and until real outcome labels and rigorous validation justify stronger prediction claims.

## The governing rule

**Do not confuse building a polished interface with validating the intelligence behind it.** The desktop product and ML research progress together, but an attractive UI must never turn a synthetic score into an asserted placement probability.

## Non-negotiable rules

1. Never claim PIS predicts hiring or placement outcomes accurately without a defensible outcome target and reproducible evaluation.
2. Treat current constructed readiness labels as synthetic proxy labels. Keep them separated from any real outcome dataset.
3. Never invent exact historical activity timestamps from aggregate GitHub or coding-platform counts.
4. Never expose one user's records to another user through an API identifier, query parameter, or client-side check.
5. Never embed server secrets, shared third-party tokens, or privileged admin credentials in the desktop bundle.
6. Do not perform a wholesale rewrite. Stabilize and evolve the useful existing Python components.
7. Every schema change must have a migration path and a clean-database test.
8. Every meaningful ML change must include a documented experiment, baseline, and evaluation decision.
9. Never promote a candidate model without validation, an artifact/version record, a smoke test, and a rollback path.
10. Run and report real checks. Do not claim a test, build, security scan, or deployment passed if it was not run.
11. Use synthetic data only in clearly labelled demo/test environments, never as hidden fallback for real-user ingestion.
12. Do not add an LLM, vector database, queue, Redis, Kubernetes, microservices, or new model family without a concrete requirement and a written rationale.

---

# 1. How to Execute This Plan with Claude Code

Use `PIS_PRD.md` as the product specification and this file as the engineering sequence. `CLAUDE.md` should point to both documents and define the repo-specific working rules. Do not ask Claude Code to implement the entire PRD in one session.

## 1.1 Recommended repository documents

Create or maintain these documents as work progresses:

- `CLAUDE.md` — concise repository map, commands, constraints, and coding workflow.
- `PIS_PRD.md` — product requirements and user-facing behavior.
- `PIS_PHASED_IMPLEMENTATION_PLAN.md` — this execution plan.
- `docs/architecture/decisions/` — short Architecture Decision Records (ADRs).
- `docs/architecture/current-state.md` — verified current architecture.
- `docs/research/` — data feasibility, research question, experiments, and conclusions.
- `docs/data-dictionary/` — feature definitions and provenance.
- `docs/runbooks/` — deployment, rollback, backup/restore, and incident procedures.

Avoid creating large amounts of empty documentation or scaffolding merely to match a folder tree. Add each document when there is real information to record.

## 1.2 Standard execution loop for every phase

For each phase, Claude Code should:

1. Read `CLAUDE.md`, `PIS_PRD.md`, this plan, and the relevant source files.
2. Inspect the working tree and current branch. Do not overwrite uncommitted user work.
3. Identify the smallest set of changes that completes the phase.
4. Present a short plan before editing if the work spans multiple files or changes architecture.
5. Implement only the selected phase. Do not begin downstream features early.
6. Run the relevant tests, linters, type checks, builds, migrations, or manual checks.
7. Fix regressions introduced by the changes. Do not conceal failures by weakening assertions or deleting tests.
8. Update documentation and examples affected by the change.
9. Report changed files, actual commands run, results, known gaps, and any decisions needing human approval.
10. Stop at the phase gate. Do not silently continue into the next phase.

## 1.3 Reusable Claude Code phase prompt

Copy this template and replace the phase number and name when starting a phase:

> Read `CLAUDE.md`, `PIS_PRD.md`, and `PIS_PHASED_IMPLEMENTATION_PLAN.md`. Implement **Phase [N]: [NAME] only**. First inspect the current working tree and the relevant implementation. Summarize the current state, the exact scope, dependencies, risks, and a file-level plan. Preserve uncommitted work. Do not implement later phases or add unrelated dependencies/features. Make the smallest coherent changes, add/update tests, run the required checks, and update documentation. Do not weaken tests to make the suite pass. Report commands actually run and whether they passed; clearly state anything not verified. If you encounter a product or architecture decision marked OPEN, do not guess: compare options and ask for a decision before hard-coding one. Finish by checking the phase's exit criteria in this plan. If any criterion remains unmet, report it and stop rather than claiming completion.

## 1.4 Definition of a completed phase

A phase is complete only when:

- All required work items are implemented or explicitly documented as blocked with an owner/decision needed.
- Every exit criterion is satisfied with evidence.
- Relevant tests pass in the declared environment.
- The documentation reflects actual behavior.
- No known severe regression remains hidden.
- The working diff is reviewable and limited to the phase.

A green unit-test suite alone does not prove production readiness, data validity, or ML quality.

---

# 2. Roadmap at a Glance

| Phase | Name | Main outcome | Must precede |
|---|---|---|---|
| 0 | Claude/repository initialization | Repo guidance and baseline map | All work |
| 1 | Reproducible baseline | Existing app can be installed, started, tested, and understood | Stabilization |
| 2 | Product and research decision gate | Clear first assessment target and data feasibility | ML redesign; production copy |
| 3 | Backend stabilization | Reliable config, schema, migrations, and tests | New account/data features |
| 4 | Domain, identity, and provenance design | Approved ownership/data model/API boundaries | Auth and ingestion implementation |
| 5 | Secure multi-user foundation | Authentication and server-side authorization | Real-user data collection |
| 6 | Correct ingestion and data quality | Truthful, traceable, fault-tolerant source data | Defensible assessments |
| 7 | ML experiment foundation | Reproducible dataset, baselines, and evaluation | Research claims |
| 8 | Versioned assessment/inference service | Safe, traceable production inference | User-facing assessment integration |
| 9 | API v1 contracts and backend workflows | Stable product API for the desktop client | Full UI integration |
| 10 | Desktop shell and design system | Runnable Tauri/React foundation | Feature UI |
| 11 | Desktop vertical slice | Login/profile/integration state end-to-end | Full product UI |
| 12 | Assessment, plan, history UX | Core user value delivered in the desktop app | Product beta |
| 13 | Privacy, export, deletion, operations | User controls and operational safety | Real beta users |
| 14 | Cross-cutting hardening | Security, reliability, accessibility, performance | Release candidate |
| 15 | Cloud staging and production deployment | Secure, observable hosted service | External testing |
| 16 | Windows installer and updates | Installable signed release candidate | Distribution |
| 17 | Release validation and launch | Documented, supportable initial release | Public release |

Some work can overlap after its contracts are agreed. In particular, desktop design exploration may begin during backend work, but production integration should not be built against unstable API assumptions.

---

# PHASE 0 — Claude Code and Repository Initialization

## Objective

Give Claude Code the right operating context and establish where source files, requirements, and implementation plans live before it starts editing code.

## Work items

### 0.1 Inspect the real repository
- Inspect the actual repository tree, not only README snippets.
- Identify entry points, services, database setup, migrations, model artifacts, tests, and Docker Compose topology.
- Confirm the active branch, working-tree changes, ignored files, and repository license.
- Do not modify application logic during initialization.

### 0.2 Create `CLAUDE.md`
Keep it short enough to remain useful. Include:
- Product description and selected stack.
- Repository map.
- Existing commands: Makefile targets and direct test commands.
- Environment setup and safe configuration rules.
- Required workflow: inspect → plan → implement → test → review.
- No-go rules around synthetic labels, provenance, security, and unsupported claims.
- Links to `PIS_PRD.md` and `PIS_PHASED_IMPLEMENTATION_PLAN.md`.
- Instruction to verify commands/files against the repo instead of assuming they exist.

### 0.3 Establish current-state documentation
Create `docs/architecture/current-state.md` only after verifying the code. It should cover:
- Request flow from API router to service/data/ML modules.
- Current database initialization path.
- How training artifacts are created and loaded.
- How GitHub and LeetCode ingestion work today.
- How Streamlit calls the API.
- Current test boundaries and untested areas.

### 0.4 Add a decision log
Create a short list of open decisions, linked to the PRD's open-decision section. Do not resolve choices by silently choosing a favorite technology.

## Deliverables
- `CLAUDE.md`
- Verified current-state architecture note
- Initial open-decision list

## Exit gate
- Claude Code can explain the existing request/data/ML flow and identify the relevant files accurately.
- No application behavior changed.
- All local edits are preserved.

---

# PHASE 1 — Reproducible Baseline and Technical Reconnaissance

## Objective

Make the current system reproducible before changing it. Record what currently works and what fails, so later improvements are measurable.

## Repository areas to inspect

- `README.md`, `Makefile`, `.env.example`, `.gitignore`
- `Dockerfile`, `docker-compose.yml`, `entrypoint.sh`
- `app/main.py`, `app/routers/*`, `app/schemas.py`, `config.py`
- `ingest/*`
- `features/compute.py`, `sql/feature_engineering*.sql`
- `ml/labels.py`, `ml/train.py`, `ml/predict.py`
- `insights/*`, `services/pipeline.py`
- `sql/schema.sql`, `sql/seed.sql`, `sql/migrations/*`
- `dashboard/*`
- `tests/*`, `requirements.txt`

## Work items

### 1.1 Run and record baseline checks
- Create a clean Python environment using the supported project setup.
- Install dependencies from the current manifest.
- Run unit tests that do not require a live database.
- Run full tests with the required database/model setup.
- Start Docker Compose from a clean database volume.
- Check API health and documented core workflows.
- Start the current Streamlit dashboard and confirm API communication.
- Record exact failures instead of trying speculative fixes first.

### 1.2 Map application workflows
Document at least:
- Health/readiness checks.
- Student/profile operations.
- GitHub ingestion.
- LeetCode/coding data ingestion.
- Feature computation.
- Prediction generation and history.
- Insight generation.
- Single-user and batch pipeline orchestration.
- Admin model retraining.

### 1.3 Inventory the current data and artifacts
- Inspect seed data, raw/scaled/labeled CSVs, model pickle files, feature-importance JSON, and their producers.
- Determine which artifacts are generated versus checked in.
- Record sample row counts and whether rows are synthetic or observed.
- Verify whether checked-in model files correspond to reproducible training code/data.
- Do not report a model metric as validated merely because an artifact exists.

### 1.4 Produce a defect register
For each issue, record severity, evidence, user impact, files, prerequisites, and suggested phase. Include at least database initialization/migration concerns, external-source data semantics, model lifecycle, configuration/secrets, testability, and current route authorization.

## Deliverables
- Baseline test/startup report under `docs/`.
- Workflow and data/artifact map.
- Prioritized defect register.
- List of verified commands for local development.

## Exit gate
- Another developer can reproduce the baseline using documented instructions.
- Known failures are recorded and not confused with newly introduced regressions.
- No broad refactor has happened yet.

---

# PHASE 2 — Product, Data-Feasibility, and ML Research Gate

## Objective

Decide what PIS can responsibly assess before redesigning the model. This phase prevents the team from building a sophisticated solution for an undefined target.

## Required decisions

### 2.1 Choose the first product claim
Choose one of these paths and document why:

**Path A — Actual outcome prediction.** Use only if legitimate, sufficiently representative, correctly timed historical outcomes can be acquired. Define the specific outcome and prediction horizon.

**Path B — Preparation intelligence.** If real outcome labels are not available, ship transparent evidence summaries, rule-based gap detection, progression tracking, and only those ML functions that have a measurable, defensible task. Do not label the output as placement probability.

The decision must be explicit. Do not keep both product interpretations in ambiguous UI copy.

### 2.2 Audit source feasibility
For each planned source, document:
- Available data and access method.
- Whether authentication is required.
- Rate limits and expected reliability.
- Data retention and platform terms to review.
- Actual temporal granularity.
- Fields that are verifiable versus inferred/unavailable.
- Failure and partial-result behavior.
- Whether the source supports the intended feature definition.

GitHub and LeetCode must be assessed separately. Do not assume that a public endpoint is a stable contract or that aggregate counts imply historical events.

### 2.3 Literature and competitive scan
Keep it narrow and useful:
- Identify existing placement-readiness products and related research.
- Search work on the selected ML task, labels, evaluation methods, and known feature limitations.
- Record the closest comparable approaches.
- Identify at least one plausible simpler baseline.
- Distinguish an existing product feature from a research contribution.

Do not spend weeks collecting papers unrelated to the selected question.

### 2.4 Define the first research question
Write one primary, testable question. Include:
- Problem statement.
- User decision it supports.
- Hypothesis.
- Target/ground truth.
- Population and unit of analysis.
- Data available at prediction time.
- Baseline method(s).
- Evaluation split strategy.
- Primary metric and why it matters.
- Secondary diagnostics.
- Minimum data feasibility requirement.
- Known risks, limitations, and failure costs.

If the team cannot define the target/data/split coherently, keep the initial product in the transparent preparation-assessment path and run a smaller methodological experiment instead.

### 2.5 Decide what counts as “research-grade” for this project
Set acceptance standards after data is known. Do not invent a generic “95% accuracy” goal. The standard should include a baseline, leakage-safe protocol, reproducibility, error analysis, and claim boundaries.

## Deliverables
- `docs/research/product-target.md`
- `docs/research/data-source-feasibility.md`
- `docs/research/literature-and-competitors.md`
- `docs/research/initial-experiment-protocol.md`
- ADR or signed-off decision for the initial assessment semantics

## Exit gate
- The product wording and initial ML research target are unambiguous.
- Data availability and source constraints are documented.
- A baseline and evaluation design are approved before model implementation.
- If valid outcome labels are not available, no implementation task may describe the product as a validated placement predictor.

---

# PHASE 3 — Stabilize the Existing Backend Foundation

## Objective

Repair current structural defects and make local execution, configuration, and database behavior dependable before introducing multi-user production features.

## Work items

### 3.1 Configuration and environment safety
- Centralize settings and validate required values at startup.
- Separate local/test/staging/production configuration.
- Replace placeholder-looking defaults that could accidentally be deployed as production credentials.
- Keep `.env.example` safe and useful with placeholders only.
- Ensure secrets are never logged or committed.
- Define clear startup errors for missing configuration.

### 3.2 Database initialization and migrations
- Audit `sql/schema.sql` and all scripts in `sql/migrations/`.
- Resolve the partial-index predicate that uses a non-immutable current-date expression. Use an index design compatible with PostgreSQL's requirements; do not replace it with another moving-date predicate.
- Resolve the discrepancy where GitHub ingestion expects a unique conflict target that may not exist in the schema created by the current Compose init path.
- Select exactly one supported migration workflow. Options include a disciplined ordered SQL migration runner or Alembic. Document the decision and avoid parallel, unsynchronized schema paths.
- Ensure fresh installs and upgrades run the same migrations in a defined order.
- Make schema failures fail loudly rather than leaving a partially initialized application.
- Define a controlled approach to seed data that cannot leak into production.

### 3.3 Persistence correctness
- Review primary/foreign keys, unique constraints, check constraints, transactions, and indexes.
- Add tests for duplicate ingestion and idempotency.
- Verify full-table and per-student SQL feature calculations have the same semantics.
- Check query parameterization and transaction cleanup.
- Confirm that connection pools are closed and errors handled correctly during startup/shutdown.

### 3.4 API reliability
- Add consistent validation/error behavior where practical without introducing API v1 prematurely in a way that breaks the current dashboard.
- Avoid raw exception details in production responses.
- Establish request IDs/correlation IDs if the current logging can support them cleanly.
- Review blocking external API calls and long-running route operations.

### 3.5 Test environment
- Make the unit-only and database integration test paths explicit.
- Use disposable database instances for integration tests.
- Add migration-from-empty checks.
- Add a minimal smoke test for API health and core pipeline behavior.

## Deliverables
- Reliable configuration module.
- Reproducible migration workflow.
- Clean database initialization.
- Updated tests and local development instructions.
- Backend stabilization report.

## Exit gate
- Clean-database initialization succeeds from zero.
- Migration scripts apply in a defined order and can be tested repeatedly.
- Existing supported core flows pass appropriate tests.
- No secrets are required in source code or hardcoded defaults.
- The current dashboard remains usable unless a documented defect intentionally blocks it.

---

# PHASE 4 — Domain Model, Identity Boundaries, and Provenance Design

## Objective

Design the multi-user data and API boundaries before adding authentication and collecting real users' data.

## Work items

### 4.1 Define core domain concepts
Specify the relationship and lifecycle for:
- User identity.
- User-owned profile.
- Integration connection.
- Sync run.
- Source observation/aggregate.
- Data-quality result.
- Feature schema and feature snapshot.
- Assessment and its evidence.
- Recommendation/action state.
- Model version and activation event.
- Audit event.
- Export/deletion request.

### 4.2 Replace assumptions around `students`
The current `students` table is a development-era entity and must not become an authorization boundary by itself. Decide how the future `users` and `profiles` concepts relate to existing student records. Provide a migration/compatibility approach rather than simply renaming tables and losing history.

### 4.3 Define provenance and missingness
Every material feature must be able to distinguish:
- Observed from an external source.
- Entered by the user.
- Derived from verified observations.
- Inferred/estimated.
- Synthetic demo/test value.
- Missing because not collected.
- Missing because a source failed.
- Stale relative to the desired observation window.
- Genuine measured zero.

Define collection time separately from event time. Never substitute one for the other.

### 4.4 Snapshot and immutability design
- An assessment should refer to the input snapshot that produced it.
- A later sync must not rewrite the old assessment's historical inputs.
- Feature definitions and schemas must be versioned.
- Decide what remains immutable and what may be recomputed.
- Document retention/deletion behavior for snapshots and backups.

### 4.5 Authorization matrix
Create a matrix for each resource and action: owner, authenticated user, operator/admin, background worker, and unauthenticated visitor. Default to denied. “The frontend does not show the button” is not authorization.

## Deliverables
- Domain model diagram or written specification.
- Data dictionary v1.
- Authorization matrix.
- Migration plan from current schema.
- ADRs for the migration and provenance representation.

## Exit gate
- All personal-data resources have a defined owner and authorization rule.
- Provenance/missingness is encoded in the data model, not merely described in UI copy.
- Assessment snapshots and model/feature versions can be traced.
- The schema can evolve without silently mixing seed/demo records with real accounts.

---

# PHASE 5 — Secure Multi-User API Foundation

## Objective

Make the API safe for multiple real users. Do this before enabling real-user ingestion or external beta access.

## Work items

### 5.1 Select the identity approach
Evaluate a managed identity provider versus a custom account/session implementation. Prefer a well-supported identity flow over custom password handling unless there is a compelling reason. Document public-client constraints: the desktop executable cannot protect a confidential client secret.

### 5.2 Implement authentication
- Sign-in and sign-out.
- Account creation or approved identity-provider onboarding.
- Email verification/recovery if required by the selected provider.
- Short-lived access credentials where appropriate.
- Secure OS-backed storage for desktop refresh/session credentials.
- Expiration, revocation, and clean re-authentication behavior.

### 5.3 Implement authorization
- Attach authenticated identity to every protected request.
- Resolve user-owned resources on the server.
- Reject unauthorized record access consistently.
- Secure every old student-oriented route that will remain accessible.
- Restrict admin operations to explicit operator/admin identities.
- Do not rely on hidden UI routes or unguessable IDs.

### 5.4 Add abuse and session protections
- Rate-limit authentication and expensive operations.
- Bound request body sizes and pagination parameters.
- Consider lockout/throttling based on identity provider capabilities.
- Ensure log output contains neither tokens nor sensitive provider payloads.
- Add tests for revoked/expired sessions.

### 5.5 Adversarial authorization tests
For every protected endpoint, test:
- User A can access their own resource.
- User B cannot access User A's resource by changing IDs.
- Anonymous requests are rejected where required.
- Regular users cannot invoke admin/model-management routes.
- Background/service identities have only the scopes they need.

## Deliverables
- Auth integration.
- Server-side authorization utilities/policies.
- Tests for owner isolation and admin boundaries.
- Auth/session architecture note.

## Exit gate
- Cross-user data access tests pass.
- Admin privileges are not inferred from a client-supplied header or static public key alone.
- The desktop bundle contains no backend secret or shared GitHub token.
- Real-user ingestion remains disabled until the gate passes.

---

# PHASE 6 — Ingestion, Data Provenance, and Data Quality

## Objective

Make every collected value truthful, explainable, and safe to use downstream.

## Work items

### 6.1 Refactor provider adapters
Keep GitHub and LeetCode/provider-specific parsing separate from domain services. Normalize provider responses into typed, validated internal observations. A provider failure must not be interpreted as a valid zero activity result.

### 6.2 GitHub integration
- Decide whether the initial flow supports public username lookup, delegated authorized access, or both.
- For delegated access, use a supported public-client authorization flow; never bundle a personal access token.
- Request the minimum scopes required.
- Handle pagination, rate limits, permission errors, timeouts, and partial responses.
- Store sync state and collection timestamps.
- Define what “commit frequency” means before computing it. Do not assign a repository aggregate count to one push date and describe it as verified daily history.
- Avoid collecting private repository metadata unless explicitly authorized and necessary.

### 6.3 LeetCode/coding-platform integration
- Verify that the intended interface is appropriate and reliable enough for the product.
- Determine exactly which fields are observed and at what temporal granularity.
- Store aggregate values as aggregates when event-level history is unavailable.
- Remove any fallback that silently generates per-problem historical timestamps for real users.
- If a reliable integration cannot be established, hide/disable it and provide an honest manual or no-data path.

### 6.4 Sync lifecycle
- Create a `sync_run` record before work begins.
- Record running/succeeded/partial/failed state, timestamps, safe error code, and counts.
- Use bounded retries and provider-aware backoff.
- Make ingestion idempotent.
- Preserve last-known-good observations after a temporary failure.
- Distinguish “no records found” from “could not retrieve records.”
- Enforce per-user cooldowns and platform rate limits.

### 6.5 Validation and quarantine
- Validate types, ranges, duplicate keys, date boundaries, and source identifiers.
- Quarantine invalid records or reject them with a traceable reason.
- Do not turn malformed values into zeros silently.
- Record parser/ingestion version where necessary to reproduce transformations.

### 6.6 Feature data contract
For every feature, document:
- Definition and units.
- Source fields.
- Event/observation window.
- Formula/SQL implementation.
- Missing-value semantics.
- Data quality requirements.
- Provenance rules.
- Version.

Implement parity tests between full-cohort and single-user feature computation.

## Deliverables
- Provider adapters with failure-safe behavior.
- Sync-run lifecycle and status API.
- Provenance-aware observations.
- Versioned feature definitions.
- Updated data dictionary and integration limitations.

## Exit gate
- No fabricated event timestamps for real accounts.
- Failed source requests cannot silently clear or overwrite good data.
- Every assessment input can be traced to observed/manual/derived/synthetic provenance.
- Integration tests cover success, empty, rate-limited, unavailable, malformed, and partial-result cases.

---

# PHASE 7 — ML Research and Experiment Foundation

## Objective

Build a reproducible experiment path and determine which ML function deserves to ship. Do not prioritize model complexity over evidence.

## Work items

### 7.1 Separate demo labels from research labels
- Make the existing weighted readiness-label generator clearly synthetic.
- Put synthetic/demo generation behind an explicit command or fixture pathway.
- Mark generated data as synthetic in artifacts and reports.
- Prevent synthetic rows/labels from entering real-world evaluation by accident.
- Do not use noisy synthetic labels to imply placement outcome variance.

### 7.2 Build a dataset audit
- Document data origin, unit of analysis, timestamps, target, coverage, missingness, duplicate risk, and permitted use.
- Inspect target leakage and post-outcome fields.
- Check whether repeated observations from the same student create dependence.
- Define a minimum dataset adequacy review before fitting ambitious models.
- Record exclusions and their rationale.

### 7.3 Build a reproducible experiment runner
Record at minimum:
- Dataset/version or fingerprint.
- Feature schema version.
- Target definition.
- Code revision.
- Dependency/runtime version.
- Configuration and random seed where applicable.
- Split identifiers/protocol.
- Baseline and candidate model parameters.
- Metrics and uncertainty where feasible.
- Artifact checksum and output report.

A full tracking platform is not automatically required; begin with reproducible artifacts and structured reports. Adopt a tracking service only if it solves a real collaboration/lifecycle problem.

### 7.4 Establish baselines
Choose baselines appropriate to the agreed research question. Examples include a naive predictor, transparent rule-based criteria, linear/logistic models, or a simple tree-based model. Baseline selection must follow the target and decision cost, not a fixed checklist.

### 7.5 Prevent evaluation leakage
- Put preprocessing, feature selection, tuning, and calibration inside the training process.
- Use temporal splits if predicting future outcomes.
- Use group-aware splits when multiple rows from one student/cohort may leak across train/test.
- Keep a final test set untouched by iterative model selection.
- Never fit a scaler or imputer using the complete dataset before splitting.
- Check features for information that would not be known at prediction time.

### 7.6 Model selection and interpretation
- Compare candidates against the baseline on the agreed primary metric.
- Conduct targeted error analysis.
- Use ablations only when they answer a specific question.
- Evaluate feature-importance or explanation stability if explanations are user-facing.
- Do not interpret feature importance as causality.
- Measure serving latency/complexity when operationally relevant.

### 7.7 Research report
Write a report that answers whether the experiment supports the hypothesis, what it does not establish, and what data or methods would improve confidence. A negative result is acceptable if it is rigorous and clearly documented.

## Deliverables
- `docs/research/dataset-card.md` or equivalent.
- `docs/research/experiment-protocol.md`.
- Baseline report.
- Reproducible experiment command.
- Versioned model/evaluation artifacts.

## Exit gate
- The selected ML task is tied to a valid target or explicitly described as non-outcome preparation intelligence.
- Baseline metrics can be reproduced.
- No leakage-prone validation path remains in the official evaluation.
- Claims in README/product copy match the evidence.

---

# PHASE 8 — Versioned Inference and Assessment Service

## Objective

Make prediction/assessment generation reliable, traceable, and safe to operate in the cloud.

## Work items

### 8.1 Define assessment types and output contracts
Distinguish at least where needed:
- Evidence summary.
- Rule-based preparation assessment.
- ML-derived output for the approved task.
- Data-quality/insufficient-evidence result.

Avoid returning an arbitrary numeric score if the required data or model is unavailable.

### 8.2 Resolve preprocessing parity
- Compare training and inference feature schemas.
- Remove unnecessary scaling for models that do not need it, or make transformations part of the persisted pipeline.
- Ensure inference applies the exact approved preprocessing.
- Validate feature order, missing values, dtypes, and schema version.
- Fail safely if an incompatible artifact or feature schema is loaded.

### 8.3 Version artifacts as a bundle
An approved version must bind together the model, preprocessing, feature schema, target semantics, and metadata. Store an artifact reference and checksum. Do not switch individual files independently while inference remains active.

### 8.4 Candidate approval and activation
- Train a candidate outside the online request path.
- Run required evaluation and smoke tests.
- Record approval status and reviewer/operator decision.
- Activate the candidate atomically.
- Keep the prior approved version available for rollback.
- Make every assessment record the exact model/rule version used.

### 8.5 Inference safety
- Handle insufficient or out-of-scope inputs explicitly.
- Validate output types and finite values.
- Bound execution time and concurrency.
- Keep training imports/jobs out of API startup where practical.
- Add prediction/assessment history using immutable snapshots.
- Separate operator-only retraining endpoints from user-facing endpoints.

### 8.6 Recommendation behavior
- Link every recommendation to evidence or a defined rule.
- State the reason and any limitations.
- Do not say the recommendation will cause a hiring outcome.
- Keep user-entered completion state separate from training labels and model truth.

## Deliverables
- Assessment domain/service contract.
- Versioned model/artifact metadata.
- Safe candidate promotion and rollback flow.
- Assessment snapshot and version metadata.
- Unit/integration tests for inference compatibility.

## Exit gate
- Every assessment is reproducible at the metadata/input-snapshot level allowed by policy.
- Deployed model version is known and observable.
- A failed candidate cannot silently replace the approved model.
- Insufficient data produces a clear non-score state instead of false precision.

---

# PHASE 9 — Stable API v1 and Backend Product Workflows

## Objective

Define the supported client/server contract before full desktop integration.

## Work items

### 9.1 API versioning
- Introduce a versioned API namespace, such as `/api/v1`.
- Keep compatibility routes only as long as needed by Streamlit/local development.
- Publish and validate the OpenAPI schema.
- Use consistent error envelopes and HTTP semantics.
- Use UTC timestamps and explicit nullability.
- Add pagination and bounded request sizes where needed.

### 9.2 Product resources
Design and implement only the routes needed for the first vertical slice and MVP:
- Current authenticated user/profile.
- Integrations and source permissions.
- Sync runs and status.
- Data-quality summary.
- Assessment create/list/detail.
- Assessment evidence.
- Recommendations and user progress state.
- Assessment history/comparison.
- User settings and deletion/export request status.
- Health/liveness/readiness endpoints.

Do not build unused endpoints solely because they appear in a proposed resource list.

### 9.3 Request lifecycle and long-running work
- External sync and other slow work should return a job/sync identifier when they cannot complete within a safe request time.
- Add a job worker only if justified by duration/retry/recovery needs; document the chosen implementation.
- Define idempotency and retry semantics.
- Keep progress and failure reasons observable.

### 9.4 Compatibility and contract tests
- Generate or validate API client types from OpenAPI where appropriate.
- Test required auth on protected routes.
- Test schema changes and error envelopes.
- Ensure no route leaks SQL, stack traces, credentials, or third-party raw payloads.

## Deliverables
- API v1 specification.
- OpenAPI contract and tests.
- Backend routes/services for the first product workflow.
- Compatibility note for current Streamlit client.

## Exit gate
- The desktop UI can be built against a stable documented contract.
- Core endpoints have owner-isolation tests.
- Error and long-running-operation states are explicit.
- Any compatibility API behavior is documented.

---

# PHASE 10 — Desktop Shell, Build System, and Design System

## Objective

Create a real Windows desktop foundation without yet building every product screen.

## Work items

### 10.1 Scaffold the application
Under a clear location such as `apps/desktop/`:
- Tauri 2 shell.
- React + TypeScript + Vite (or approved equivalent).
- Strict TypeScript checks.
- Lint/format/build/test commands.
- Environment handling for API base URL without secrets.
- Development and production build configurations.

Avoid duplicating the backend under the desktop folder.

### 10.2 Establish Tauri security boundaries
- Use a minimum capability/permission set.
- Do not enable unrestricted shell or filesystem access by default.
- Validate external links and navigation.
- Decide which APIs are handled by the browser frontend and which require Tauri capabilities.
- Design secure token persistence before implementing auth.

### 10.3 Add shared frontend foundations
- Application routing and shell.
- Typed API client layer.
- Centralized request/response and error handling.
- Design tokens, typography, spacing, colors, and component patterns.
- Reusable loading, empty, partial, stale, and error states.
- Accessible form fields, buttons, dialogs, and navigation.
- App-level connection state.

### 10.4 Product visual exploration
Design and validate the shell and a small number of representative screens before scaling components. Visual design should emphasize clarity and evidence, not arbitrary charts or decorative “AI” effects.

### 10.5 Test infrastructure
- Frontend unit/component tests.
- Type checking and production build in CI.
- Basic Tauri build smoke check where runners permit.
- Document local dev workflow.

## Deliverables
- Runnable desktop window.
- Frontend quality commands and CI.
- Design tokens and app shell.
- Secure capability configuration.

## Exit gate
- Windows development build launches.
- No backend secrets are bundled.
- Lint, type check, tests, and build run from documented commands.
- The app can show API-unavailable and loading states without crashing.

---

# PHASE 11 — First Desktop Vertical Slice: Sign-In to Real Profile State

## Objective

Prove the entire desktop-to-cloud route with one small, secure, end-to-end workflow before adding more screens.

## Scope

The initial slice should support:
1. Launch desktop app.
2. Sign in through the approved auth mechanism.
3. Load current user's profile.
4. Display backend connection/service status.
5. Display integration states.
6. Sign out and handle expired sessions.

## Work items

### 11.1 Session flow
- Implement the selected sign-in flow.
- Store session material with a suitable OS-backed mechanism.
- Handle cancellation, expiry, refresh failure, and logout.
- Avoid logging auth payloads.

### 11.2 Profile flow
- Fetch the authenticated user's profile.
- Show useful empty state when no profile exists.
- Validate and save profile edits.
- Handle conflict/error responses.

### 11.3 Typed API integration
- Use the API v1 contract.
- Ensure all backend requests carry the correct auth context.
- Handle revoked permissions and network errors centrally.
- Do not silently replay non-idempotent operations after retries.

### 11.4 End-to-end tests
Test sign-in, profile load/update, logout, expired token, backend unavailable, and cross-user denial at the API level.

## Deliverables
- One end-to-end account/profile flow.
- Tested session handling.
- First Windows desktop CI artifact, even if not yet public.

## Exit gate
- A test user can sign in and load only their own profile through the packaged/development desktop app.
- Session expiry and backend outage are understandable and recoverable.
- No credentials are stored in plaintext app settings or logs.

---

# PHASE 12 — Core Product UX: Integrations, Assessment, Development Plan, History

## Objective

Deliver the core value of PIS in the desktop app, using the verified backend APIs and accurate assessment semantics.

## Work items

### 12.1 Integrations screen
- Display supported provider, permissions, connection status, latest sync attempt, latest successful sync, and data categories collected.
- Provide connect/reconnect, sync, disconnect, and delete-imported-data actions where supported.
- Show rate-limit, partial-success, missing-permission, and provider-outage states distinctly.
- Provide explicit consent/preview for data collection.

### 12.2 Overview screen
- Show last assessment time and data freshness.
- Show a concise summary and a small number of priorities.
- Do not display an assessment score until the backend says the data is sufficient.
- Do not show fake live metrics or hardcoded sample performance in production.

### 12.3 Assessment screen
- Show evidence and feature definitions.
- Identify source and collection time where relevant.
- Distinguish observed metrics, user-entered values, rules, and ML estimates.
- Include relevant caveats and limitations.
- Link to the snapshot/model/feature version details in a human-readable way.

### 12.4 Development Plan screen
- Show actionable priorities linked to evidence.
- Allow the user to track planned/in-progress/completed/dismissed status if implemented.
- Explain that recommendations are suggestions, not guarantees of employment outcomes.
- Keep editorial content separate from predictions.

### 12.5 History screen
- List prior assessments.
- Compare two snapshots only when the comparison is meaningful.
- Disclose changes in data coverage and feature/model versions.
- Preserve the historical result's original input reference.

### 12.6 Shared UX details
- Keyboard navigation and visible focus states.
- Empty/loading/stale/offline/partial-data/error states.
- Bounded UI retries and clear retry actions.
- Avoid duplicate fetches and request races.
- No charts without a specific user decision they help answer.

## Deliverables
- Integrations, Overview, Assessment, Development Plan, and History screens.
- API integration tests and UI tests for primary workflows.
- Product copy reviewed against the actual ML/data limitations.

## Exit gate
- A user can connect/sync a supported source, inspect data quality, run/view an assessment, inspect evidence, follow recommendations, and review history.
- Every data-driven screen handles empty/incomplete/stale/error states.
- Historical comparisons disclose incompatible versions or coverage changes.

---

# PHASE 13 — Privacy Controls, Export/Deletion, and Operator Workflows

## Objective

Give users meaningful control over their data and operators enough control to run the system safely.

## Work items

### 13.1 Integration controls
- Disconnect source.
- Revoke/remove stored authorization where possible.
- Optionally remove imported source data with clear confirmation.
- Document effects on previous assessments and history.

### 13.2 Export and account deletion
- Export the user's own stored data in a documented format.
- Ensure the export includes useful metadata but not secret tokens.
- Implement account deletion flow and status tracking.
- Define what happens to assessments, source observations, recommendations, audit records, and backups.
- Ensure deleted accounts cannot continue using old sessions.
- Verify backup retention behavior and disclose the policy.

### 13.3 Consent and privacy center
- Show what data is stored and why.
- Separate core processing from optional research/training use.
- Provide a way to review/revoke optional consent where appropriate.
- Keep policy text consistent with implementation.

### 13.4 Operator features
- Secure admin identity/role.
- Model version status and activation history.
- Sync/job failure inspection using sanitized diagnostics.
- Audit events for sensitive operations.
- No ability to browse personal profile data by default unless the operational task and access policy specifically justify it.

## Deliverables
- Data export and deletion workflows.
- Privacy/settings interface.
- Audit trail and operator policy.
- Updated privacy/data-retention docs.

## Exit gate
- Users can export and request deletion of their own data.
- Revoked sessions/integrations stop being used.
- Sensitive operations are audited without recording secrets.
- The retention policy covers primary storage, replicas, and backups.

---

# PHASE 14 — Cross-Cutting Hardening

## Objective

Run targeted quality, security, accessibility, and reliability work before staging acceptance.

## Work items

### 14.1 Security review
- Re-run authorization boundary tests across all user-owned routes.
- Audit secrets in tracked files, build outputs, logs, and desktop bundles.
- Scan dependencies and assess high-severity findings.
- Check query parameterization and input validation.
- Verify rate limits and request size limits.
- Review CORS/callback/deep-link behavior where applicable.
- Inspect Tauri capabilities for least privilege.
- Test update signing once configured.

### 14.2 Reliability review
- External API timeout, partial-failure, and retry scenarios.
- Database restart and connection interruption.
- Worker/job restart behavior if workers exist.
- Failed model activation and rollback.
- Failed migration recovery and backup restore.
- Stale token and expired integration grants.

### 14.3 Performance baseline
- Measure common API p50/p95 under a documented test load.
- Profile slow database queries against representative fixtures.
- Measure cold desktop startup and common-screen responsiveness.
- Verify external calls do not block the UI thread.
- Optimize only measured bottlenecks.

### 14.4 Accessibility and usability
- Keyboard-only walkthrough.
- Focus and contrast review.
- Empty/error-state review.
- Ensure status is not communicated by color alone.
- Test realistic laptop window sizes and scaling.

### 14.5 Test suite quality
- Separate unit/integration/e2e commands.
- Remove brittle network dependencies from unit tests.
- Test source failure modes with fixtures/mocks.
- Retain regression tests for every fixed defect.
- Ensure tests do not rely on developer-specific paths or real personal API tokens.

## Deliverables
- Security/privacy review report.
- Reliability test report.
- Performance baseline.
- Accessibility issues resolved or explicitly tracked.
- Release blocker list.

## Exit gate
- No unresolved critical security/privacy issue.
- All high-risk authorization and data-integrity flows are tested.
- Backup restore, model rollback, and failed-sync recovery are demonstrated.
- Performance targets are measured; exceptions are documented.

---

# PHASE 15 — Cloud Staging and Production Deployment

## Objective

Deploy the backend to a controlled staging environment, exercise the production-like setup, then promote only after acceptance.

## Work items

### 15.1 Select and document hosting
Evaluate:
- Managed PostgreSQL and version support.
- Secret management.
- Networking and access controls.
- Backups and restore capability.
- Logs/metrics/alerts.
- Region, latency, privacy, and data residency needs.
- Deployment workflow and rollback.
- Expected cost and budget alerts.

Do not choose hosting by popularity alone; record the trade-off in an ADR.

### 15.2 Create environment separation
- Local, test, staging, and production are distinct.
- Distinct credentials and database instances.
- No seed data in production.
- Production access is restricted.
- All production configuration is injected securely.

### 15.3 Container/service deployment
- Build immutable backend images/artifacts.
- Run schema migrations as a controlled release step.
- Configure health/readiness probes.
- Set CPU/memory/timeouts appropriate to the chosen host.
- Use least-privilege DB identity and restricted network access.
- Establish rollback to the last working application release.

### 15.4 Observability and operations
- Structured logs with request IDs.
- Error/latency metrics.
- Database connection and capacity monitoring.
- Sync success/failure and job duration metrics.
- Model version in relevant assessment diagnostics.
- Alerts for critical outages, repeated job failures, and backup failure.
- Credential rotation and incident response runbooks.

### 15.5 Backups and recovery
- Enable scheduled encrypted backups.
- Define retention.
- Perform a restore drill.
- Document recovery point/recovery time objectives based on realistic needs.

### 15.6 Staging acceptance
Run end-to-end tests with the actual deployed API and staging database, using synthetic/test accounts only. Validate source integrations with approved test identities where possible.

## Deliverables
- Infrastructure/deployment configuration.
- Staging and production runbooks.
- Monitoring and alerts.
- Backup/restore evidence.
- Deployment and rollback procedure.

## Exit gate
- Staging passes all critical end-to-end workflows.
- Production secrets are managed outside source control and desktop artifacts.
- Database backups and restoration are tested.
- Rollback is rehearsed.
- No production deployment is used as the first real integration test.

---

# PHASE 16 — Windows Installer, Signing, Updates, and Clean-Machine Validation

## Objective

Make PIS genuinely installable and maintainable by a regular user.

## Work items

### 16.1 Installer metadata
- Product name/version/publisher.
- App icon and file metadata.
- Stable application identifier.
- Installer/uninstaller behavior.
- Versioned release notes.
- Appropriate architecture target.

### 16.2 Build pipeline
- Produce installers reproducibly from tagged/release commits.
- Keep signing credentials outside CI source/config files.
- Verify build outputs and publish checksums.
- Archive release metadata and tested commit hash.
- Do not bundle `.env`, tokens, local databases, training data, or developer-only paths.

### 16.3 Code signing and update safety
- Choose and configure a supported signing strategy.
- Protect signing keys and updater endpoints/metadata.
- Verify update integrity before install.
- Define rollback and recovery if update fails.
- Decide whether updates are automatic, prompted, or manually downloaded.
- Make the chosen behavior clear to users.

### 16.4 Clean-machine installation matrix
Test on a clean supported Windows environment with no developer toolchain:
- Fresh install.
- First launch.
- Sign in.
- Backend unavailable.
- Normal workflow.
- Upgrade from previous build.
- Failed/aborted update where safely testable.
- Uninstall/reinstall behavior.
- DPI/display scaling and common window sizes.

### 16.5 Distribution materials
- Installation guide.
- Support/troubleshooting page.
- Checksums and release notes.
- Privacy policy/terms links.
- Known issues.

## Deliverables
- Signed or appropriately verified Windows installer.
- Release build pipeline.
- Clean-machine test results.
- Install/update/uninstall guide.

## Exit gate
- A non-developer can install and use PIS without Python, Node.js, Docker, or PostgreSQL.
- No secrets or local development artifacts are included.
- Updates preserve user access and have a documented failure recovery path.

---

# PHASE 17 — Release Candidate and Launch

## Objective

Release only when the product, engineering, data, and ML claims have each met their own standard.

## Work items

### 17.1 Product acceptance
Walk through the end-to-end journey using a clean test account. Confirm onboarding, profile, source consent, sync, assessment, evidence, development plan, history, settings, export/deletion, and recovery states.

### 17.2 ML/product-claim review
- Review every label and headline that sounds predictive.
- Confirm all displayed scores have documented semantics.
- Confirm no placement probability appears unless appropriately validated.
- Review the model card and dataset notes.
- Confirm the current model version and limitations are exposed appropriately.

### 17.3 Operational checklist
- Verify dashboards/alerts.
- Verify backup and restore state.
- Verify credentials are rotatable.
- Verify rollback procedure.
- Verify support route and incident contact.
- Verify database migration/release notes.

### 17.4 Release documentation
- Release notes.
- Installation and onboarding guide.
- Privacy/terms.
- API/developer setup where repository contributors need it.
- Research/evaluation summary with limitations.
- Known issues and support path.

### 17.5 Controlled rollout
Start with a small, explicitly invited test group if the product is not yet proven at scale. Monitor sync failures, crashes, confusing assessments, and support feedback. Do not interpret early engagement as evidence of ML validity.

## Deliverables
- Release candidate checklist.
- Versioned installer and backend release.
- User-facing documentation.
- Known-limitations record.
- Post-release monitoring plan.

## Exit gate
- Every P0 PRD requirement is complete or has an explicitly accepted, documented exception.
- Critical user journeys pass on a clean machine and the deployed staging/production-like backend.
- No critical security/privacy issue remains.
- ML/product claims are truthful and tied to evidence.
- The rollback/support plan is usable by someone other than the original developer.

---

# 3. Cross-Phase Engineering Rules

## 3.1 Change management

- Work in small feature branches or small, reviewable commits.
- One phase can contain several commits; do not combine unrelated phases into one giant commit.
- Keep generated files out of commits unless intentionally versioned and documented.
- Never force-push or reset user work unless explicitly requested.
- Before a risky migration, create a reproducible test fixture and recovery plan.

## 3.2 Test policy

A change must include tests at the lowest useful level and higher-level tests for boundary behavior. For example:
- A feature formula change needs deterministic unit tests and parity checks.
- A route authorization change needs tests for owner and non-owner requests.
- A migration needs clean-install and upgrade tests.
- A model change needs a reproducible experiment report, not just a unit test.
- A desktop workflow needs UI/API tests and, for release-critical journeys, end-to-end validation.

Never weaken the intended behavior just to obtain a green test run. When a test is invalid, explain why and replace it with an appropriate assertion.

## 3.3 Dependency policy

Before adding a dependency, answer:
1. What concrete requirement does it meet?
2. Can the current stack meet the requirement with less complexity?
3. Is the dependency actively maintained and license-compatible?
4. What is its effect on bundle size, security, build reproducibility, and deployment?
5. How will it be tested and updated?

Pin/lock dependencies according to the chosen tooling. Do not casually upgrade the entire dependency tree during a feature task.

## 3.4 ML artifact policy

- No pickle/model artifact is trusted merely because it is in the repository.
- Artifacts must be produced by known training code and recorded with provenance/checksum.
- Only compatible, approved artifacts load into production inference.
- Never load arbitrary user-uploaded model files.
- Keep large/generated artifacts out of Git unless there is a safe, intentional fixture use case.

## 3.5 API and frontend policy

- Backend is the authority for authentication, authorization, calculations, and data correctness.
- Frontend validation improves usability but does not replace backend validation.
- Do not ship provider credentials or model artifacts that should remain server-side.
- Do not hardcode demo response data in production screens.
- API errors must be mapped into safe, useful user feedback.
- API contracts should be versioned and tested before broad client integration.

## 3.6 Scope control

Do not add the following to the initial release without evidence and an approved change:
- A chat-based AI assistant.
- LLM-generated career advice.
- Embeddings/vector search.
- Multi-agent orchestration.
- Autonomous model retraining/deployment.
- Public student rankings.
- A job marketplace or recruiter portal.
- Offline inference.
- Multi-platform desktop release.

These may be explored later if a demonstrated user need and risk review support them.

---

# 4. First Three Sessions: Exactly What to Do Now

## Session 1 — Claude initialization only

1. Put `PIS_PRD.md` and this plan where Claude Code can read them from the repository root (or document their actual paths in `CLAUDE.md`).
2. Run the initialization/onboarding flow you intend to use.
3. Ask Claude Code to inspect the repository and draft a concise `CLAUDE.md`.
4. Require it to list the current entry points, commands, main data flow, open defects, and files it could not verify.
5. Do not let this session rewrite the backend or scaffold the desktop app.
6. Review and commit the repository guidance after it is accurate.

## Session 2 — Baseline verification

1. Start from a clean working tree or record existing changes.
2. Execute Phase 1 using the standard prompt.
3. Have Claude record exact test results, clean database startup behavior, and current end-to-end flows.
4. Fix only blockers required to reproduce the baseline if they prevent the audit; otherwise record them for Phase 3.
5. Produce a prioritized defect register.

## Session 3 — Product/ML decision gate

1. Execute Phase 2.
2. Investigate whether valid placement-outcome labels can realistically be obtained.
3. Validate the true data granularity and access limitations of each integration.
4. Choose the initial product target and research question.
5. Do not start model redesign until the decision and evaluation protocol are written down.

After these sessions, proceed one phase at a time. Avoid launching parallel Claude sessions that edit the same files or independently design competing schemas.

---

# 5. Release Gates Summary

Before real user data:
- [ ] Clean schema/migrations verified.
- [ ] User identity and authorization implemented.
- [ ] Cross-user access tests pass.
- [ ] Secret/token handling reviewed.
- [ ] Provenance and deletion model implemented.
- [ ] External-source permissions/limitations documented.

Before showing an assessment as ML-driven:
- [ ] Target and intended use documented.
- [ ] Features represent actual, correctly timed evidence.
- [ ] Baseline and evaluation protocol approved.
- [ ] Preprocessing and splitting are leakage-safe.
- [ ] Metrics/error analysis reproduced.
- [ ] Model and feature versions recorded.
- [ ] Claim language reviewed.

Before desktop beta:
- [ ] Stable API contract.
- [ ] Sign-in/profile/integration vertical slice works.
- [ ] Key UI screens and failure states work.
- [ ] Data export/deletion policy is implemented or beta scope is explicitly constrained.
- [ ] No critical authorization/security issue remains.

Before public desktop release:
- [ ] Cloud staging passes critical end-to-end flows.
- [ ] Monitoring, alerting, backup, and restore are verified.
- [ ] Installer/update/signature strategy is tested on clean Windows.
- [ ] Privacy/terms/support documentation is available.
- [ ] All public ML/product claims are supported.
- [ ] Rollback and incident procedures are documented.

---

# 6. Final Execution Principle

**PIS is not complete when it has more files, more models, or a prettier dashboard. It is complete when a real user can install it, understand what it does, trust the provenance of the evidence, control their data, and receive outputs whose claims are supported by reproducible engineering and ML evaluation.**
