# Placement Intelligence System (PIS)

> Product specification; parts predate the implementation. The implementation plan that accompanied it was deleted from the repo (commit `e1fc2cd`) and is historical.

## Product Requirements Document (PRD)

**Document status:** Proposed product direction\
**Version:** 1.0\
**Last updated:** 13 October 2026\
**Product type:** Cloud-connected desktop application\
**Primary desktop target:** Windows 10/11, 64-bit\
**Working repository:** `PIS-main`\
**Current implementation:** Python, FastAPI, PostgreSQL, scikit-learn,
SQL feature engineering, Streamlit\
**Proposed desktop client:** Tauri 2 + React + TypeScript\
**Proposed backend:** FastAPI + Python\
**Proposed primary database:** Managed PostgreSQL\
**Audience:** Product, engineering, ML, QA, security, and future
contributors

> **Purpose of this document:** Define the intended product, users,
> functionality, architecture, ML research standards, migration
> approach, quality requirements, and acceptance criteria for evolving
> the existing PIS repository into a trustworthy, research-grade ML
> product delivered through an installable desktop application connected
> to a cloud backend.

------------------------------------------------------------------------

# 1. Executive Summary

The Placement Intelligence System (PIS) is evolving from a locally run,
Docker-based student placement-readiness prototype into a polished,
cloud-connected desktop product.

A user should be able to download a signed Windows installer, install
PIS without installing Python or PostgreSQL, launch the application,
create an account, connect supported developer-profile sources, review
the data collected, run an assessment, understand the evidence behind
the results, and follow a personalized development plan.

The desktop application will be the primary user experience. The cloud
backend will own authentication, authorization, data ingestion, feature
computation, ML inference, prediction history, and controlled model
deployment. PostgreSQL will remain the primary server-side relational
database. The existing FastAPI and Python codebase is a foundation to
audit and evolve, not a reason to preserve every implementation detail
unchanged.

The product must distinguish three concepts that are currently too easy
to conflate:

1.  **Observed evidence:** Data actually obtained from a source, with
    provenance and collection time.
2.  **Preparation assessment:** A transparent description of observed
    activity and identified development areas.
3.  **Outcome prediction:** A statistical estimate of a clearly defined
    real-world outcome, available only if suitable outcome labels and
    validation evidence support it.

PIS must not claim to predict hiring success accurately merely because a
model produces a numerical score. Existing synthetic labels may be
retained for deterministic development fixtures and pipeline testing,
but must not be presented as real placement outcomes or used to
substantiate claims of predictive validity.

The product will be developed in staged releases. First, establish a
reliable and secure foundation. Next, define and validate the ML
problem. Then build the desktop experience and distribution pipeline.
Finally, evaluate whether a local/offline mode or additional data
sources are justified.

## 1.1 Product vision

**Help students understand their current preparation, identify
evidence-backed skill gaps, and make better decisions about what to
improve next, through a transparent and scientifically evaluated
intelligence system.**

## 1.2 Product principles

-   **Evidence before scores.** Every displayed assessment must explain
    which data supports it.
-   **Honest ML.** No unsupported claims of hiring probability,
    accuracy, fairness, or generalization.
-   **Useful before complicated.** Add models and services only when
    they address a measured need.
-   **Desktop-first experience.** PIS should feel like a real installed
    application, not a browser page in a wrapper.
-   **Cloud-managed intelligence.** The backend controls data access,
    model versions, and inference.
-   **Privacy by design.** Collect only what is necessary, explain why,
    and provide deletion controls.
-   **Reproducibility.** Data definitions, experiments, model artifacts,
    and evaluation results must be traceable.
-   **Incremental evolution.** Preserve useful existing capabilities
    while replacing defective or unsubstantiated behavior.
-   **No hidden synthetic data.** Generated fixtures must be labelled as
    synthetic and must never masquerade as real activity.
-   **Measurable releases.** Every release has explicit acceptance
    criteria.

------------------------------------------------------------------------

# 2. Current Repository Baseline

This section describes the repository as inspected from the supplied
`PIS-main.zip`. It is a design baseline, not a claim that all current
behavior has passed runtime verification.

## 2.1 Current stack

  -----------------------------------------------------------------------
  Area                                Current implementation
  ----------------------------------- -----------------------------------
  API                                 FastAPI, Uvicorn, Pydantic

  Database                            PostgreSQL 15, `psycopg2`
                                      connection pool

  Feature engineering                 SQL CTEs, including full-table and
                                      single-student queries

  ML                                  scikit-learn Random Forest
                                      regressor and classifier

  Preprocessing                       `MinMaxScaler` persisted as a model
                                      artifact

  Data ingestion                      GitHub REST API; LeetCode public
                                      GraphQL endpoint; synthetic
                                      generators

  Insights                            Rule-based weakness detection plus
                                      model feature-importance ranking

  UI                                  Three-page Streamlit dashboard
                                      using an HTTP API client

  Packaging/development               Docker Compose, Dockerfiles,
                                      Makefile, environment variables

  Tests                               pytest tests covering core logic,
                                      API contracts, pipeline, insights,
                                      and mocked external API clients

  Model files                         Pickled regressor/classifier/scaler
                                      and feature-importance JSON
  -----------------------------------------------------------------------

## 2.2 Existing repository areas to preserve or evaluate

-   `app/main.py`: FastAPI app setup, startup validation, health
    endpoints, request logging.
-   `app/routers/students.py`: Student CRUD and student history/status
    endpoints.
-   `app/routers/ingest.py`: Coding and GitHub ingestion endpoints.
-   `app/routers/features.py`: Feature retrieval.
-   `app/routers/predictions.py`: Prediction generation and retrieval.
-   `app/routers/insights.py`: Insight report generation.
-   `app/routers/pipeline.py`: Single-student and batch orchestration.
-   `app/routers/admin.py`: Model retraining trigger and status.
-   `app/schemas.py`: API request/response schemas.
-   `ingest/`: External API clients, synthetic generators, validation,
    and DB connections.
-   `features/compute.py`: Feature computation and scaling.
-   `ml/labels.py`: Current constructed-label generation.
-   `ml/train.py`: Training, evaluation, and model artifact generation.
-   `ml/predict.py`: Model inference and prediction persistence.
-   `insights/`: Rules and composite insight generation.
-   `services/pipeline.py`: Multi-step ingestion-to-insight
    orchestration.
-   `sql/schema.sql`: Database tables and indexes.
-   `sql/feature_engineering.sql`: Full-table feature computation.
-   `sql/feature_engineering_single.sql`: Parameterized single-student
    computation.
-   `sql/ranking.sql`: Ranking query.
-   `sql/migrations/`: Existing migration scripts.
-   `dashboard/`: Current Streamlit UI and HTTP client.
-   `tests/`: Existing automated test suite.
-   `docker-compose.yml`, `Dockerfile`, `dashboard/Dockerfile`,
    `entrypoint.sh`: Current local deployment and startup flow.

## 2.3 Existing data model

The current schema includes the following core entities:

-   `students`: name, email, branch, CGPA, platform usernames, creation
    time, and sync timestamps.
-   `coding_activity`: student, problem identifier, difficulty, and
    solve date.
-   `github_activity`: student, repository name, commit count, and date.
-   `features`: computed aggregate features per student.
-   `predictions`: latest readiness score and category per student.
-   `prediction_history`: time-series history of generated readiness
    scores.

The production data model will require changes for authentication, user
ownership, consent, source-sync runs, provenance, model versions,
experiment/evaluation metadata, audit events, and more robust prediction
records.

## 2.4 Existing feature set

The current model uses five primary inputs:

-   `cgpa`
-   `total_problems`
-   `avg_difficulty`
-   `consistency_score`
-   `commit_frequency`

These features can be useful for experimentation, but their definitions,
validity, completeness, and relationship to the chosen target must be
re-evaluated before being used for high-confidence claims.

## 2.5 Known risks and required audit items

The following are known or previously identified risks in the current
implementation. Each must be confirmed and tracked through
implementation rather than assumed fixed.

1.  **Constructed target labels:** `ml/labels.py` derives readiness
    labels from a weighted formula with noise. This is a synthetic proxy
    target, not actual placement outcomes.
2.  **LeetCode temporal provenance:** The current ingestion approach can
    derive aggregate counts and generate per-problem timestamps that do
    not represent verified historical solve dates. Such generated dates
    must not be treated as actual behavior.
3.  **GitHub activity semantics:** Aggregated commit counts associated
    with repository update/push dates do not necessarily represent
    actual daily commit history. The feature definition needs correction
    or explicit qualification.
4.  **Small development dataset:** Checked-in feature samples and seed
    students are development fixtures, not an adequate research dataset.
5.  **Database initialization and migrations:** The schema and migration
    strategy require an audit, including the use of non-immutable
    expressions in index predicates and ensuring required constraints
    exist on fresh installations.
6.  **Model preprocessing/evaluation:** Preprocessing must be fitted
    only within the appropriate training folds. Scaling requirements
    should be justified for each model.
7.  **Model retraining and in-memory state:** Retrained artifacts must
    be validated and activated as a versioned unit. Replacing files on
    disk must not leave the running service using an unintended old
    model.
8.  **Multi-user security:** Existing student-oriented endpoints and
    shared database design must not be assumed safe for public
    multi-user deployment without authentication, authorization,
    ownership isolation, and abuse controls.
9.  **Credentials and secrets:** Development defaults and admin-key
    patterns must not be carried into production.
10. **Runtime validation:** A repository-level review is not equivalent
    to passing tests against a real database or deployed environment.
    Runtime, migration, packaging, and integration validation remain
    release gates.

## 2.6 Existing capabilities that should not be discarded without evidence

-   SQL-first feature engineering.
-   Separate single-student and full-table computation paths.
-   Pydantic validation.
-   External API clients with mocked tests.
-   Rule-based explanations.
-   Prediction history.
-   Pipeline cooldowns and batch limits.
-   Model retraining status.
-   Health checks.
-   Docker-based local development.
-   Existing API/UI separation.

The goal is to improve the product, not to rewrite the repository
indiscriminately.

------------------------------------------------------------------------

# 3. Product Goals and Non-Goals

## 3.1 Primary goals

### G1. Ship an installable desktop application

A non-technical user should be able to install and launch PIS on a
supported Windows computer without manually installing Python, Node.js,
Docker, PostgreSQL, or a local API server.

### G2. Provide a trustworthy personal preparation assessment

Users should be able to inspect their connected data, review data
freshness, understand the limits of the assessment, and receive useful
next steps.

### G3. Establish a defensible ML research process

PIS must have a clearly defined target, appropriate baselines,
leakage-safe evaluation, reproducible experiments, documented
limitations, and versioned artifacts.

### G4. Preserve and improve the existing Python backend

The current FastAPI, SQL, ingestion, feature, ML, and insight components
should be audited and refactored where justified rather than replaced
automatically.

### G5. Make cloud operation secure and maintainable

The backend must support authenticated users, tenant-safe data access,
database migrations, monitoring, backups, controlled model deployment,
and operational recovery.

### G6. Deliver an excellent desktop UX

The application should feel responsive, coherent, accessible, and
intentionally designed, with clear loading, empty, error, and
degraded-connectivity states.

### G7. Make results explainable and traceable

Every assessment must be tied to the input snapshot, feature
definitions, model/rules version, creation time, and relevant evidence.

## 3.2 Secondary goals

-   Export a personal report.
-   Track assessment history and meaningful progress.
-   Support GitHub as the first well-defined external integration.
-   Support LeetCode only to the extent that the available interface
    provides legitimate, reliable, and accurately described data.
-   Support synthetic demo mode for onboarding and testing, visibly
    labelled.
-   Establish CI/CD for backend, frontend, desktop packaging, and ML
    validation.
-   Make future macOS support possible without promising it in the first
    release.

## 3.3 Non-goals for the first production release

-   Guaranteeing job offers, internships, or placement success.
-   Claiming that PIS can objectively measure a person's overall
    engineering ability from GitHub or coding-platform activity.
-   Replacing a university's placement office or recruiter judgment.
-   Scraping private accounts or bypassing source-platform access
    controls.
-   Building a social network, job board, or recruitment marketplace.
-   Automatically messaging recruiters or applying to jobs.
-   Introducing an LLM, vector database, multi-agent framework, or
    deep-learning model without a validated use case.
-   Supporting all operating systems on day one.
-   Requiring users to host their own backend or database.
-   Showing public leaderboards by default.
-   Ranking students against one another without explicit authorization,
    appropriate consent, and a valid product rationale.
-   Training on personal user data without clear disclosure and
    appropriate consent.
-   Presenting synthetic data as genuine observations or synthetic
    targets as actual placement outcomes.

------------------------------------------------------------------------

# 4. Target Users and Jobs to Be Done

## 4.1 Primary persona: Student building employable skills

**Context:** A college student wants to understand their current
preparation and decide what to improve next.

**Needs:** - A quick, understandable starting assessment. - A clear
explanation of the evidence used. - Identification of data gaps and
stale integrations. - Prioritized actions rather than generic
motivational advice. - A way to track progress over time. - Control over
connected accounts and stored information.

**Job to be done:** "Help me understand what my current evidence shows,
what it cannot show, and which concrete actions are most likely to
improve my preparation."

## 4.2 Secondary persona: Student conducting a technical self-audit

**Context:** A technically curious user wants to inspect features,
evidence, model behavior, and changes across assessments.

**Needs:** - Feature-level details and definitions. - Data provenance
and sync timestamps. - Historical comparisons. - Clear distinctions
between measured facts, rules, and ML-derived outputs. - Exportable
reports and reproducible assessments where possible.

**Job to be done:** "Let me inspect the reasoning and data behind my
assessment rather than treating a score as a black box."

## 4.3 Future persona: Authorized placement coordinator

This persona is not automatically included in the first release.

A coordinator may need aggregate cohort views, but such a product
requires explicit institutional authorization, role-based access, a
valid legal/privacy basis, cohort-level permissions, and careful
handling of sensitive educational data. Individual assessments must not
become visible to coordinators or peers by default.

## 4.4 Administrator/operator persona

**Needs:** - Service health and deployment status. - Model version and
evaluation reports. - Retraining job status. - Data-sync failure
visibility. - Audit logs. - Safe rollback. - Controlled access to
operational functions.

Administrative capabilities must not be exposed to ordinary desktop
users.

------------------------------------------------------------------------

# 5. Product Positioning and Value Proposition

## 5.1 Positioning

PIS is a **personal preparation intelligence application** that converts
verified development and academic evidence into transparent assessments
and prioritized next steps.

It is not a hiring oracle.

## 5.2 Core value proposition

"Understand your preparation with evidence, not guesswork."

## 5.3 Differentiation hypotheses to test

These are hypotheses, not established competitive advantages:

1.  Data provenance is visible rather than hidden.
2.  Assessment explanations distinguish measured evidence, deterministic
    rules, and ML output.
3.  Recommendations are prioritized and linked to specific gaps.
4.  Progress comparisons use consistent definitions and disclose changes
    in data coverage.
5.  The application is installable and straightforward to use.
6.  ML claims are backed by reproducible experiments rather than
    demo-only metrics.

A competitive landscape review must test these hypotheses before they
are used as external marketing claims.

------------------------------------------------------------------------

# 6. Product Scope and Release Strategy

## 6.1 Release 0: Foundation and technical stabilization

Purpose: make the existing system safe to evolve.

Scope: - Reproduce the current application locally. - Run unit tests and
integration tests with a real disposable PostgreSQL instance. - Repair
schema/migration inconsistencies. - Remove unsafe production defaults. -
Document current endpoints and data semantics. - Add configuration
validation. - Establish baseline CI. - Separate production behavior from
synthetic demo behavior. - Define ownership and data provenance
requirements. - Create an architecture decision record for the
desktop/cloud model.

Exit criteria: - Clean database initialization succeeds. - All
migrations can run from an empty database and from the supported
previous schema. - Tests pass in a documented environment. - External
API failures are distinguishable from legitimate empty results. -
Synthetic data is explicitly labelled. - No critical known defect is
silently accepted.

## 6.2 Release 1: Secure cloud API and defensible assessment foundation

Scope: - Authentication and authorization. - User-owned profiles. -
User-specific integrations. - Secure credential/token storage
strategy. - Provenance-aware ingestion and sync status. - Versioned
feature definitions. - A defined assessment contract. - Versioned
prediction/assessment records. - Safe model loading and deployment. -
API versioning and contract tests. - Initial ML evaluation report. - No
unsupported outcome-prediction claim.

Exit criteria: - One user cannot access another user's data by changing
an identifier. - API credentials are not embedded in the desktop
client. - Every assessment references its input snapshot and
implementation/model version. - The system can distinguish real,
missing, stale, and synthetic data. - ML target and evaluation
methodology are documented and reviewed.

## 6.3 Release 2: Windows desktop MVP

Scope: - Tauri desktop shell. - React + TypeScript UI. - Authentication
and onboarding. - Personal profile setup. - GitHub connection or
username-based public-data flow, depending on the approved integration
design. - Data preview and consent. - Sync status. - Assessment
overview. - Evidence and feature details. - Recommendations. -
Assessment history. - Settings, privacy controls, and sign-out. - Signed
installer and release artifacts. - Automatic or clearly guided update
strategy, selected before release.

Exit criteria: - Installation works on a clean supported Windows
machine. - No developer toolchain is required by the end user. - Login,
data sync, assessment, history, sign-out, and deletion flows work
end-to-end. - The UI communicates API failures and stale data
accurately. - A user can understand the difference between assessment
and actual placement probability.

## 6.4 Release 3: Research-grade ML iteration

Scope: - Literature and competitor review. - Dataset inventory and
access/consent review. - Target and cohort definition. - Strong baseline
models. - Leakage-safe temporal or group-aware evaluation as
appropriate. - Calibration and uncertainty analysis where appropriate. -
Subgroup and robustness analysis where sample sizes and legal/ethical
conditions permit. - Error analysis and ablation studies. - Experiment
tracking and model registry or equivalent versioned artifact process. -
Model cards and data documentation. - Retraining gates and rollback. -
Publication-quality methodology documentation if results justify it.

Exit criteria: - A reproducible experiment can be run from documented
inputs. - Reported metrics can be independently reproduced. - Claims are
restricted to the population, time period, and target supported by the
evaluation. - A failed candidate model cannot replace the approved
model. - Limitations and known failure modes are documented.

## 6.5 Later releases, subject to evidence

-   Optional offline/local mode.
-   macOS support.
-   Authorized cohort analytics.
-   Additional verified data sources.
-   Advanced time-series or graph-based methods if data justifies them.
-   Optional generated coaching summaries, if they add value and can be
    constrained to evidence-backed facts.
-   Institutional deployment only after privacy, access-control, and
    operational requirements are defined.

------------------------------------------------------------------------

# 7. Functional Requirements

Priority labels: - **P0:** Required for first production release. -
**P1:** Important follow-up capability. - **P2:** Future or
evidence-dependent capability.

## 7.1 Desktop installation and lifecycle

### FR-DESK-001 --- Installable application (P0)

PIS must be distributed as a Windows installer. The user must not need
to install Python, Node.js, Docker, PostgreSQL, or run shell commands.

**Acceptance criteria** - A clean Windows 10/11 x64 test machine can
install and launch the application using documented steps. - Installer
failure produces an actionable message. - The application has a product
name, version, icon, and publisher metadata. - The application can be
uninstalled using standard Windows mechanisms. - The installer does not
overwrite user data without an explicit migration policy.

### FR-DESK-002 --- Application startup (P0)

On launch, PIS must show an intentional startup state while it checks
local configuration and backend reachability.

**Acceptance criteria** - The UI never appears frozen during normal
network checks. - The user can distinguish "connecting," "service
unavailable," "authentication required," and "ready." - Network timeouts
are bounded. - A transient outage does not crash the desktop process.

### FR-DESK-003 --- Updates (P0)

Define a secure update mechanism before public distribution.

**Acceptance criteria** - Update artifacts are authenticated or
signature-verified using the selected distribution mechanism. - The app
displays current and available versions accurately. - Failed updates
leave the previously installed application usable. - Update checks do
not transmit unnecessary personal data.

### FR-DESK-004 --- Desktop navigation (P0)

The application must support predictable navigation between Dashboard,
Assessment, Development Plan, History, Integrations, and Settings.

### FR-DESK-005 --- Diagnostics (P1)

Users can generate a sanitized diagnostic report containing app version,
OS version, API reachability, and non-sensitive error identifiers.
Tokens, passwords, private profile data, and raw secrets must never be
included.

## 7.2 Account and onboarding

### FR-AUTH-001 --- Account lifecycle (P0)

Users can create an account, authenticate, sign out, and recover access
through the selected identity mechanism.

The identity provider or email-verification mechanism must be selected
during architecture design. Do not invent or embed a client secret in
the desktop bundle.

### FR-AUTH-002 --- Session handling (P0)

Sessions must use secure, revocable tokens or an equivalent safe session
mechanism.

**Acceptance criteria** - Access tokens are short-lived where
practical. - Refresh/session credentials are stored using an appropriate
operating-system secure-storage mechanism. - Logout invalidates the
local session and revokes server-side sessions where supported. -
Expired sessions lead to a clear re-authentication flow. - Secrets are
not stored in plaintext application settings or logs.

### FR-ONBOARD-001 --- First-run onboarding (P0)

Guide the user through: 1. Welcome and explanation of what PIS does and
does not claim. 2. Account setup or sign-in. 3. Basic profile setup. 4.
Optional integration connection. 5. Data preview and consent. 6. First
sync. 7. Initial assessment, only when required data is available. 8.
Explanation of results and limitations.

The user must be able to skip optional integrations and return to them
later.

### FR-ONBOARD-002 --- Demo mode (P1)

Provide a clearly marked demo using synthetic data.

**Acceptance criteria** - Demo profiles are labelled "Sample data." -
Demo values cannot be confused with the user's actual profile. -
Synthetic records are excluded from research training and production
performance reporting unless a separately documented experimental
protocol explicitly includes them. - Switching to a real account does
not silently merge demo data.

## 7.3 Profile and academic information

### FR-PROFILE-001 --- Profile management (P0)

Users can view and update their own profile fields needed by the
product.

Candidate fields include display name, academic branch/program,
graduation year, and CGPA if the assessment design justifies collecting
it.

Every field must have a documented purpose. Optional fields should
remain optional unless they are necessary for a specific disclosed
feature.

### FR-PROFILE-002 --- Input validation (P0)

Validate all inputs on the client for usability and on the server for
security and correctness.

### FR-PROFILE-003 --- Data correction (P0)

Users must be able to correct or remove manually entered data.
Assessment history must clearly indicate when a profile edit changes the
inputs used by a later assessment.

### FR-PROFILE-004 --- Data minimization (P0)

Do not collect student roll numbers, precise location, demographic
information, private academic records, or other sensitive fields unless
a documented requirement and appropriate privacy review justify them.

## 7.4 External integrations and data ingestion

### FR-INT-001 --- Integration catalog (P0)

The app must show supported integrations, their connection state, last
successful sync, last attempted sync, and the categories of data
collected.

### FR-INT-002 --- GitHub integration (P0)

Support a documented GitHub data-collection flow.

Preferred options must be evaluated: - OAuth/device authorization or
another approved delegated authorization flow for
private/user-authorized data. - Public username-based retrieval for
public data only, with a clear explanation of its limitations.

The desktop client must not contain a shared GitHub personal access
token. OAuth client configuration is not a substitute for protecting
client secrets; desktop clients are public clients.

The ingestion service must follow GitHub rate limits, handle pagination,
retry transient failures safely, and distinguish an empty profile from a
failed request.

### FR-INT-003 --- LeetCode integration (P1, conditional)

Before shipping, verify that the selected endpoint/interface is
appropriate for the intended use, stable enough for support, and
consistent with the platform's applicable terms and constraints.

Do not promise unsupported historical activity. If only aggregate
statistics are available, store and display them as aggregates. Do not
manufacture historical solve dates from aggregate counts.

If reliable integration cannot be established, provide manual input or
omit the integration rather than silently falling back to fabricated
activity.

### FR-INT-004 --- Explicit sync (P0)

Users can trigger a sync and see progress, completion time, records or
metrics updated where appropriate, and any partial failures.

### FR-INT-005 --- Scheduled/refresh sync (P1)

If periodic sync is introduced, it must be configurable,
rate-limit-aware, and transparent to the user.

### FR-INT-006 --- Data provenance (P0)

Every ingested value must be traceable to: - Source platform or manual
input. - Collection timestamp. - Source object or endpoint category
where appropriate. - Sync-run identifier. - Data
transformation/version. - Provenance class: observed, user-entered,
inferred, or synthetic. - Validity/quality status.

Never represent inferred or synthetic timestamps as observed timestamps.

### FR-INT-007 --- Sync failures (P0)

Failures must not silently replace good data with empty data or
synthetic values. Partial success must be represented explicitly.

### FR-INT-008 --- Data freshness (P0)

The UI must show when each source was last successfully synchronized and
whether the assessment relies on stale or incomplete data.

### FR-INT-009 --- Disconnect integration (P0)

Users can disconnect a source and choose whether to delete previously
imported source data. Explain the consequences before deletion.

### FR-INT-010 --- Rate limiting and cache (P0)

Apply bounded retries, source-aware caching, rate-limit handling, and
per-user sync cooldowns. A force-refresh action must still respect
platform constraints.

## 7.5 Data quality and feature engineering

### FR-DATA-001 --- Versioned feature definitions (P0)

Each feature must have a documented definition, unit, allowed range,
source, missing-value behavior, observation window, and version.

### FR-DATA-002 --- No fabricated historical activity (P0)

Do not infer exact daily activity from aggregate counts. If the source
only exposes an aggregate, preserve that semantic level.

### FR-DATA-003 --- Missing-data semantics (P0)

Missing data must not automatically be converted into zero unless zero
is semantically correct. Represent missing, unavailable, not connected,
stale, and genuine zero as distinguishable states.

### FR-DATA-004 --- Data validation (P0)

Validate source responses and persisted records for schema, ranges,
duplicates, timestamps, and impossible values. Reject or quarantine
invalid records with a safe diagnostic.

### FR-DATA-005 --- Reproducible feature snapshots (P0)

An assessment must reference the exact feature snapshot used for
inference. A later data sync must not silently mutate the historical
inputs of an old assessment.

### FR-DATA-006 --- SQL and migrations (P0)

Use a defined migration system and test migrations against a clean
database and supported prior versions. Schema initialization must not
rely on undocumented manual steps.

### FR-DATA-007 --- Feature computation consistency (P0)

The full-table and single-user feature paths must use consistent
definitions and produce equivalent results for the same valid input
snapshot.

### FR-DATA-008 --- Data-quality report (P1)

Show completeness, freshness, provenance, and warnings relevant to the
assessment. Do not expose raw internal SQL or secrets.

## 7.6 Assessment and ML inference

### FR-ML-001 --- Explicit target definition (P0)

Before any model is described as predicting placement outcomes,
document: - Target variable and exact definition. - Prediction time and
horizon. - Eligible population. - Outcome source and label quality. -
Feature availability at prediction time. - Exclusion criteria. -
Intended decision/use. - Known biases and limitations.

If trustworthy outcome labels are unavailable, the initial product must
describe its output as a preparation assessment or evidence-based
profile, not as a validated hiring probability.

### FR-ML-002 --- Baseline-first model development (P0)

Establish simple, appropriate baselines before evaluating complex
models.

Possible baselines depend on the chosen target and may include constant
predictors, simple rule-based approaches, logistic/linear models, or
tree-based models. Selection must be justified rather than mechanically
applying every algorithm.

### FR-ML-003 --- Leakage-safe evaluation (P0)

Preprocessing, feature selection, threshold tuning, calibration, and
model selection must occur inside training partitions or nested
validation as appropriate.

Use temporal splits when the deployment task predicts future outcomes
from historical data. Use group-aware splits where repeated observations
from the same student or cohort could leak information across
partitions. A random split must not be used merely because it produces
better metrics.

### FR-ML-004 --- Reproducible experiments (P0)

Record dataset/version identifiers, feature schema version, code
revision, random seeds where applicable, configuration,
environment/dependencies, metrics, model artifacts, and experiment
notes.

### FR-ML-005 --- Model registry/versioning (P0)

Each deployed model must have a unique version and metadata including
training data reference, feature schema, training code revision,
evaluation results, creation time, and approval status.

### FR-ML-006 --- Model activation safety (P0)

A candidate model must pass validation and smoke tests before
activation. Activation must be atomic at the logical bundle level.
Failed deployment must preserve the last approved model.

### FR-ML-007 --- Assessment provenance (P0)

Each result must record: - Assessment ID and user ID. - Input snapshot
ID. - Feature schema version. - Model version or rule-engine version. -
Creation timestamp. - Data-quality warnings. - Output type and intended
interpretation. - Applicable confidence/uncertainty metadata, if
properly supported.

### FR-ML-008 --- No unsupported probability language (P0)

A score must not be labelled "chance of placement," "probability of
getting hired," or equivalent unless the model predicts a precisely
defined outcome and probability quality is validated for the target
population.

### FR-ML-009 --- Uncertainty and abstention (P1)

Where appropriate and validated, the system should show uncertainty or
decline to produce an assessment when the data is insufficient, out of
distribution, or outside supported conditions. Do not fabricate
numerical confidence intervals.

### FR-ML-010 --- Error analysis (P0)

ML releases must include analysis of false positives, false negatives,
error distributions, and failure cases appropriate to the target.

### FR-ML-011 --- Model monitoring (P1)

Monitor input distribution changes, missingness, prediction
distribution, latency, and performance once delayed ground-truth labels
become available. Input drift alone must not be presented as proof of
declining model accuracy.

### FR-ML-012 --- Retraining governance (P0)

Retraining is an operator-controlled workflow in the first production
release. Candidate models must be evaluated and approved before
promotion. Do not automatically retrain and deploy solely because a
drift detector fired.

## 7.7 Assessment presentation

### FR-ASSESS-001 --- Assessment overview (P0)

Show a concise summary of the current assessment, date, input-data
freshness, overall interpretation, and highest-priority development
areas.

### FR-ASSESS-002 --- Evidence breakdown (P0)

For each displayed insight, identify the evidence and distinguish: -
Directly observed metric. - User-entered information. - Deterministic
rule. - ML-derived estimate. - Inference that has not been independently
validated.

### FR-ASSESS-003 --- Feature definitions (P0)

Users can inspect what a feature measures, its unit, source, time
window, and known limitations.

### FR-ASSESS-004 --- No false precision (P0)

Do not show more numerical precision than the data and model justify.
Scores should have documented semantics and stable interpretation.

### FR-ASSESS-005 --- Category labels (P0)

If labels such as "Ready," "Near Ready," or "Needs Improvement" remain,
they must be backed by documented criteria and tested against the
target. Otherwise replace them with descriptive, non-outcome-claiming
language.

### FR-ASSESS-006 --- Empty and incomplete states (P0)

If the user has no connected source, insufficient data, or stale data,
show a useful explanation and a next step instead of a misleading score.

### FR-ASSESS-007 --- Historical comparisons (P0)

Comparisons must show dates and disclose material changes in feature
definitions, source coverage, or model versions. Do not compare scores
across incompatible versions as if they were directly equivalent.

## 7.8 Development plan and recommendations

### FR-PLAN-001 --- Prioritized actions (P0)

Show a manageable set of concrete actions, each with: - Gap or objective
addressed. - Evidence that motivated it. - Why it matters. - Suggested
action. - Completion or review condition where appropriate. - Whether
the action is rule-based, model-derived, or editorial.

### FR-PLAN-002 --- Non-generic recommendations (P0)

Avoid recommendations that merely restate a feature threshold.
Recommendations should be actionable and appropriately scoped to the
evidence.

### FR-PLAN-003 --- No causal overclaim (P0)

Do not claim that changing a metric will cause a better placement
outcome unless supported by appropriate causal evidence. Phrase advice
as a hypothesis or practical suggestion when causality is unknown.

### FR-PLAN-004 --- Progress tracking (P1)

Allow users to mark actions as planned, in progress, completed, or
dismissed. These states describe the user's workflow and must not be
mistaken for ML outcome labels.

### FR-PLAN-005 --- Recommendation evaluation (P1)

Where feasible, evaluate recommendation usefulness through user feedback
and observed engagement without treating engagement as proof of
employment impact.

## 7.9 Assessment history and reports

### FR-HIST-001 --- History list (P0)

Users can review prior assessments and their timestamps.

### FR-HIST-002 --- Snapshot comparison (P0)

Users can compare assessments based on their respective stored input
snapshots and versions.

### FR-HIST-003 --- Export report (P1)

Allow export of a personal report, preferably PDF and/or CSV where
appropriate. Reports must include generation time, data sources,
freshness, feature definitions/version, model/rules version,
limitations, and a clear disclaimer.

### FR-HIST-004 --- Deletion behavior (P0)

Deleting an account or data source must have documented effects on
source data, features, assessments, history, and backups. Where
retention in backups is time-limited, disclose the retention period.

## 7.10 Settings, privacy, and account controls

### FR-SET-001 --- Integration settings (P0)

Users can view, reconnect, refresh, and disconnect integrations.

### FR-SET-002 --- Data export (P1)

Users can request an export of their own data in a documented format.

### FR-SET-003 --- Account deletion (P0)

Users can request deletion of their account and associated personal
data, subject to clearly disclosed legal/security retention
requirements.

### FR-SET-004 --- Privacy summary (P0)

Explain what is collected, why, where it is processed, how long it is
retained, and whether it is used for model training.

### FR-SET-005 --- Model-training consent (P0)

Personal user data must not be repurposed for training or research
beyond the disclosed product purpose without an appropriate legal basis
and explicit consent where required. Product operation and optional
research participation must be separable.

## 7.11 Operations and administration

### FR-OPS-001 --- Health monitoring (P0)

Expose safe operational health checks for API, database, and
model-serving readiness.

### FR-OPS-002 --- Administrative authorization (P0)

Administrative endpoints must use a proper authenticated role or service
identity. A static admin key is not a sufficient long-term public
administration design.

### FR-OPS-003 --- Audit trail (P0)

Record security-relevant events such as authentication failures,
permission changes, data deletion requests, integration changes, model
activation, and administrative operations. Avoid logging tokens or
unnecessary personal data.

### FR-OPS-004 --- Background jobs (P1)

Long-running sync, batch assessment, and training tasks should use an
explicit job lifecycle if synchronous API execution is insufficient. Job
state must be observable and recoverable after worker restarts.

### FR-OPS-005 --- Backup and restore (P0)

Define automated database backups, retention, encryption, and periodic
restore tests before storing real user data in production.

------------------------------------------------------------------------

# 8. Desktop UX and Information Architecture

## 8.1 Proposed primary navigation

1.  **Overview**
2.  **Assessment**
3.  **Development Plan**
4.  **History**
5.  **Integrations**
6.  **Settings**

A compact account/profile area and a persistent sync/connection
indicator may appear in the application shell.

Administrative model-management features belong in a protected operator
interface, not in the ordinary student navigation.

## 8.2 Overview screen

Purpose: answer "Where do I stand, and what should I do next?"

Contents: - Greeting and profile context. - Last assessment timestamp. -
Data freshness and source status. - Assessment summary. - Top
development priorities. - Recent progress indicators. - Clear warnings
if data is incomplete or the assessment cannot be interpreted
reliably. - Primary actions: Sync data, Review assessment, View
development plan.

Do not fill the screen with charts simply because the data is numeric.

## 8.3 Assessment screen

Contents: - Summary interpretation. - Evidence and feature breakdown. -
Data source and timestamp for each metric. - Rules or model
explanation. - Missingness and data-quality warnings. -
Model/feature-definition version details in a suitably accessible "How
this was generated" section. - Limitations relevant to the current
result.

## 8.4 Development Plan screen

Contents: - Prioritized recommendations. - Why each recommendation
exists. - Expected effort or suggested cadence only where reasonable. -
Progress status. - Links to relevant learning resources only when the
links are maintained and verified. - No fabricated guarantees about
score or hiring improvement.

## 8.5 History screen

Contents: - Chronological assessment list. - Current versus previous
comparison. - Data coverage changes. - Model/feature version changes. -
Export action. - Clear indication when two assessments are not directly
comparable.

## 8.6 Integrations screen

Contents: - Supported sources. - Connected/disconnected state. -
Permission scope. - Last successful sync and last attempt. - Data
categories imported. - Sync button and progress. - Error recovery
guidance. - Disconnect and delete-imported-data actions.

## 8.7 Settings screen

Contents: - Profile. - Account/session. - Privacy and consent. - Data
export/deletion. - Notifications and sync preferences, if implemented. -
App version. - Diagnostics. - Terms and privacy-policy access.

## 8.8 UX states required throughout the app

Every network-backed screen must handle: - Initial loading. -
Refreshing. - Empty state. - Partial data. - Stale data. -
Authentication expired. - Offline/no network. - Backend unavailable. -
Rate-limited integration. - Validation failure. - Recoverable error. -
Unrecoverable error with safe diagnostic reference.

Do not show an infinite spinner or silently swallow errors.

## 8.9 Visual design direction

The final visual system is to be designed, not assumed. Recommended
principles: - Desktop-native information density without clutter. -
Clear hierarchy and readable typography. - Restrained use of color for
status and priority. - Consistent spacing and component behavior. -
High-quality empty, loading, and error states. - Accessible contrast and
keyboard navigation. - Motion only when it clarifies state or
hierarchy. - No excessive gradients, fake terminal aesthetics, or
decorative charts that do not support decisions. - Responsive behavior
for common laptop window sizes.

The design must be validated with real screens and user workflows before
the visual system is locked.

------------------------------------------------------------------------

# 9. Technical Architecture

## 9.1 Recommended high-level architecture

``` text
┌──────────────────────────── USER DEVICE ─────────────────────────────┐
│                                                                      │
│  PIS Desktop                                                         │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Tauri 2 shell                                                  │  │
│  │ React + TypeScript UI                                          │  │
│  │ Typed API client                                               │  │
│  │ Secure OS-backed session storage where supported              │  │
│  │ Minimal non-sensitive preferences/cache                        │  │
│  └────────────────────────────┬───────────────────────────────────┘  │
└───────────────────────────────┼──────────────────────────────────────┘
                                │ HTTPS
                                │ Authenticated, versioned API
                                ▼
┌──────────────────────────── CLOUD ───────────────────────────────────┐
│  Edge / TLS / rate limiting                                          │
│             │                                                        │
│  FastAPI application                                                 │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Authentication + authorization                                 │  │
│  │ Profile and integration services                               │  │
│  │ Ingestion and sync jobs                                         │  │
│  │ Data validation and provenance                                  │  │
│  │ Feature computation                                             │  │
│  │ Assessment and insight services                                 │  │
│  │ Model registry/activation interface                             │  │
│  │ Audit events and observability                                  │  │
│  └───────────────┬───────────────────────────┬────────────────────┘  │
│                  │                           │                       │
│                  ▼                           ▼                       │
│        Managed PostgreSQL            Background worker (when needed) │
│                  │                           │                       │
│                  └──────────────┬────────────┘                       │
│                                 ▼                                    │
│                      Versioned model artifacts                       │
│                      + evaluation metadata                           │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    Approved external source APIs
```

## 9.2 Desktop technology

**Proposed:** Tauri 2 + React + TypeScript.

Rationale: - Produces an installable desktop application. - Allows a
modern React interface. - Avoids requiring users to install a separate
browser or Python runtime. - Provides a clear boundary between UI and
desktop capabilities. - Can support Windows packaging first and other
platforms later.

The exact Tauri plugins, secure storage approach, updater, signing, and
permissions must be reviewed before implementation. Use the smallest
capability set possible.

The desktop application should not host the authoritative database or ML
model state in its local UI bundle.

## 9.3 Frontend conventions

Recommended: - TypeScript strict mode. - A shared typed API client. -
Runtime validation for untrusted API responses where useful. -
Centralized auth/session handling. - Centralized error mapping. -
Reusable loading/empty/error components. - Unit tests for domain logic
and components. - End-to-end tests for critical user flows. - Design
tokens and accessible reusable UI primitives.

State-management and data-fetching libraries should be selected based on
demonstrated complexity, not added by default.

## 9.4 Backend technology

Retain FastAPI and Python unless an audit demonstrates a specific reason
to replace them.

Required backend boundaries: - API routers: HTTP validation and response
mapping. - Application/services layer: use cases and orchestration. -
Domain layer: feature definitions, assessment semantics, rules, and
domain validation. - Data-access layer: database queries and
transactions. - Integration adapters: GitHub and any approved
coding-platform integration. - ML layer: training/evaluation separated
from online inference. - Operations layer: health, metrics, audit
events, model activation.

Avoid importing HTTP router code directly into domain or ML modules.

## 9.5 Database

Retain PostgreSQL as the cloud system of record.

Introduce a reliable migration tool and a versioned migration workflow.
Existing hand-maintained migration scripts can be adopted or replaced
only through a planned migration.

Use foreign keys, unique constraints, appropriate indexes, and
transaction boundaries. Do not rely on the desktop client for
authorization or data integrity.

Do not introduce Redis, a task queue, object storage, or a model
registry service until an explicit requirement justifies it. A worker
and artifact store may become appropriate as sync, training, or artifact
volume grows.

## 9.6 Background jobs

Use background workers for tasks that exceed a safe request duration or
need retry/recovery semantics, such as: - Source synchronization. -
Batch assessment. - Dataset preparation. - Model training and
evaluation. - Report generation.

The job system must record status, safe error summaries, start/end time,
retries, and idempotency behavior. The specific technology is an
implementation decision after measuring requirements.

## 9.7 Cloud environment strategy

At minimum, define separate environments: - Local development. -
Automated test/CI. - Staging. - Production.

Each environment must have separate credentials and data. Production
data must not be copied into development fixtures without approved
anonymization and access controls.

Infrastructure provider selection remains open. Evaluate cost, managed
PostgreSQL availability, secret management, backups, deployment
simplicity, observability, region, and ability to export data before
committing.

## 9.8 API versioning and compatibility

-   Introduce a versioned API namespace, such as `/api/v1`, before the
    desktop client depends on the production contract.
-   Document request and response schemas.
-   Use consistent error response shapes.
-   Use pagination for potentially large collections.
-   Define timeouts and retry policies.
-   Use idempotency keys for relevant operations.
-   Deprecate endpoints deliberately.
-   Do not expose internal exception strings, SQL details, stack traces,
    tokens, or environment configuration.

The current unversioned endpoints should be treated as a migration
baseline, not necessarily the final public contract.

------------------------------------------------------------------------

# 10. Proposed Domain Model Evolution

The existing schema is a starting point. The final schema must be
designed and migrated deliberately.

Potential entities:

## 10.1 `users`

-   `id` (UUID or equivalent stable identifier)
-   `identity_provider_subject` or equivalent identity reference
-   `email` if required by the identity mechanism
-   `created_at`
-   `updated_at`
-   `status`

Do not store unnecessary identity data.

## 10.2 `profiles`

-   `id`
-   `user_id`
-   `display_name`
-   `branch_or_program` (optional)
-   `graduation_year` (optional)
-   `cgpa` (optional, if justified)
-   `created_at`
-   `updated_at`

A user should own their profile. Avoid using a globally visible
`student_id` as the authorization boundary.

## 10.3 `integration_connections`

-   `id`
-   `user_id`
-   `provider`
-   `connection_status`
-   `granted_scopes` or permission summary
-   `connected_at`
-   `last_sync_attempt_at`
-   `last_successful_sync_at`
-   `disconnected_at`
-   secret/token reference, never a plaintext token in ordinary
    application tables

Secrets should be encrypted and access-controlled using a dedicated
strategy appropriate to the chosen deployment.

## 10.4 `sync_runs`

-   `id`
-   `user_id`
-   `provider`
-   `status`
-   `started_at`
-   `completed_at`
-   `records_observed`
-   `records_created`
-   `records_updated`
-   `records_rejected`
-   `safe_error_code`
-   `source_snapshot/reference`
-   `ingestion_version`

Do not store full raw API payloads indefinitely without a documented
need and retention policy.

## 10.5 `source_observations`

Represents source-backed records or aggregates, with provenance.

Candidate fields: - `id` - `user_id` - `provider` - `observation_type` -
`source_object_id` where available - `observed_at` - `collected_at` -
`sync_run_id` - `provenance_type` - `payload_version` - normalized
values needed for the product - `quality_status`

Exact table design depends on the selected source semantics. Avoid a
generic JSON blob as the only representation of important analytical
fields.

## 10.6 `feature_snapshots`

-   `id`
-   `user_id`
-   `created_at`
-   `feature_schema_version`
-   `source_coverage`
-   `quality_summary`
-   normalized feature values
-   references to source snapshot/sync runs

A normalized child table or versioned JSON representation may be
appropriate depending on query patterns. The choice must preserve schema
validation and reproducibility.

## 10.7 `assessments`

-   `id`
-   `user_id`
-   `feature_snapshot_id`
-   `assessment_type`
-   `assessment_version`
-   `model_version` nullable for rule-only assessments
-   `status`
-   `created_at`
-   `interpretation`
-   `quality_warnings`
-   `output_payload_version`

## 10.8 `assessment_history` or immutable assessment records

Store prior assessment results and relevant metadata without silently
rewriting historical outputs when the current model changes.

## 10.9 `recommendations`

-   `id`
-   `assessment_id`
-   `recommendation_code`
-   `priority`
-   `evidence_reference`
-   `explanation`
-   `status` (planned/in progress/completed/dismissed)
-   `created_at`
-   `updated_at`

## 10.10 `model_versions`

-   `id`
-   `name`
-   `version`
-   `artifact_reference`
-   `artifact_checksum`
-   `feature_schema_version`
-   `training_dataset_reference`
-   `code_revision`
-   `metrics_summary`
-   `approval_status`
-   `created_at`
-   `activated_at`
-   `retired_at`

## 10.11 `audit_events`

-   `id`
-   `actor_user_id` nullable for system events
-   `event_type`
-   `resource_type`
-   `resource_id`
-   `created_at`
-   safe metadata
-   request/correlation identifier

Never include credentials or full sensitive payloads in audit metadata.

## 10.12 Migration requirements

-   Every schema change must have an ordered migration.
-   Migrations must be tested from an empty database.
-   Supported upgrade paths must be documented.
-   Destructive migrations require explicit backup and rollback/recovery
    plans.
-   Production migration execution must be controlled, logged, and
    observable.
-   Avoid running automatic schema mutation at arbitrary application
    startup in production.

------------------------------------------------------------------------

# 11. ML Research and Evaluation Plan

This section is a mandatory product workstream, not optional polish.

## 11.1 Research problem gate

Before selecting an advanced model, answer:

1.  What precise question is PIS attempting to answer?
2.  What is the target variable?
3.  At what time is the prediction made?
4.  What future period or decision does it relate to?
5.  What data is legitimately available at prediction time?
6.  Where do labels come from?
7.  How representative is the dataset of intended users?
8.  What would a useful prediction change for the user?
9.  What harm could a false positive or false negative cause?
10. What simpler method is the model expected to improve upon?

If these questions cannot be answered, do not market the output as a
validated outcome prediction.

## 11.2 Two valid initial research directions

### Option A: Actual outcome prediction

Only proceed if suitable historical outcome data can be obtained
lawfully and with an appropriate privacy/consent basis.

Example target candidates, to be selected and precisely defined: -
Whether a participant receives a qualifying internship offer within a
specified future window. - Whether a participant passes a defined
assessment stage. - Another clearly observable outcome relevant to the
intended user decision.

Requirements: - Exact target definition. - Label provenance and quality
checks. - Prediction-time cutoff to prevent post-outcome leakage. -
Appropriate cohort/time-based evaluation. - Calibration and threshold
analysis where probabilistic output is used. - Subgroup/error analysis
where feasible and appropriate. - Explicit limitations for missing or
biased data.

PIS must not claim that a target is validated merely because labels can
be collected.

### Option B: Preparation assessment and development intelligence

Use this direction if trustworthy placement-outcome labels are not
available.

PIS can still provide value by: - Summarizing verified activity. -
Identifying gaps relative to transparent, user-understandable
criteria. - Tracking changes in observed behavior. - Detecting anomalous
or incomplete data. - Recommending concrete development actions. -
Investigating a narrower ML problem supported by available data.

Potential research questions must be evaluated individually. Examples
include: - Does a data-quality-aware feature pipeline reduce erroneous
assessments compared with a naive pipeline? - Can a method detect
meaningful changes in activity while distinguishing source-data failures
from actual behavioral changes? - Do evidence-linked recommendations
improve user-reported usefulness compared with generic rule-based
advice?

These are candidate hypotheses, not established contributions. The first
research milestone is a literature and data feasibility review.

## 11.3 Dataset governance

Every dataset must have: - Owner/source. - Collection and access
method. - Permission/consent basis. - Population and coverage
description. - Time range. - Missingness summary. - Label definition and
provenance. - Known biases. - Data version/hash or equivalent
reproducibility reference. - Retention and deletion rules. - Approved
use, including whether it can be used for training.

Synthetic data: - Must be generated through explicit fixture or
simulation code. - Must be labelled synthetic at every relevant
interface and export. - Must not be merged invisibly with real data. -
Must not be used to claim real-world performance. - May be used for
pipeline tests, UI demos, stress tests, and controlled robustness
experiments, clearly identified as such.

## 11.4 Evaluation methodology

Depending on the target and data structure: - Establish a simple
baseline. - Split data by time, student/group, cohort, or a justified
combination. - Fit all preprocessing only on training data. - Keep final
test data isolated from model/threshold selection. - Use nested
validation where model-selection bias is material. - Report uncertainty
around metrics when feasible. - Document the population to which results
may generalize. - Analyze failure cases rather than only aggregate
scores. - Use a fixed random seed when applicable, while also checking
sensitivity to seed variation where useful. - Compare against a
rule-based baseline if the product already has rule logic. - Include
compute and latency cost when operationally relevant.

Metric selection must follow the target: - Classification: metrics such
as precision, recall, F1, PR-AUC, ROC-AUC, balanced accuracy,
calibration, and cost-sensitive measures as appropriate. - Regression:
MAE, RMSE, calibration/residual analysis where meaningful, and a
baseline-relative measure. - Ranking: NDCG, precision/recall at K, or
other appropriate ranking metrics. - Time-series/anomaly detection:
event-level precision/recall, false alarms per time period, detection
delay, and alert utility where appropriate.

Do not report every metric mechanically. Explain which metrics drive the
decision and why.

## 11.5 Model comparison and complexity gate

A more complex model is accepted only if it: - Addresses a defined
limitation of a baseline. - Improves a relevant metric or provides a
justified operational benefit. - Has a reproducible evaluation. - Does
not introduce unacceptable latency, cost, interpretability, or
maintenance burden. - Has documented failure modes.

Candidate models could include linear/logistic baselines, random
forests, gradient-boosted trees, or specialized temporal/graph models if
the research question and data justify them. Model choice remains open.

## 11.6 Interpretability

-   Feature importance is not causal evidence.
-   Tree impurity importance must not be presented as "what causes
    placement success."
-   Explanation methods must be appropriate to the selected model and
    evaluated for stability where important.
-   User-facing explanations must not invent a causal story from
    correlation.
-   Explainability output must refer to the exact model and input
    snapshot used.

## 11.7 Calibration and uncertainty

If PIS exposes a probability, evaluate whether predicted probabilities
correspond to observed frequencies for the defined target and intended
population.

If a score is only a heuristic or normalized index, label it as such.

If data is insufficient or outside supported conditions, PIS may show an
"insufficient evidence" state rather than produce a number.

## 11.8 Model cards and experiment reports

Every candidate model should have a report containing: - Intended use
and prohibited uses. - Target and population. - Training/evaluation data
provenance. - Feature schema. - Evaluation design. - Baselines. -
Metrics and uncertainty. - Calibration, if relevant. - Error analysis. -
Known limitations and failure modes. - Performance/cost profile. -
Version and artifact checksum. - Approval decision and reviewer.

------------------------------------------------------------------------

# 12. Security, Privacy, and Responsible Use

## 12.1 Threat model

Threats include: - Unauthorized access to another user's profile or
assessment. - Stolen session tokens. - Leaked third-party credentials. -
API scraping or abusive automated requests. - Insecure desktop updater
or tampered installer. - Model artifact replacement. - Sensitive
information leaking through logs or error messages. - SQL injection or
unsafe query construction. - Dependency/supply-chain compromise. -
Excessive retention of source data. - Misleading or discriminatory
assessment claims. - Abuse of administrative endpoints.

## 12.2 Authentication and authorization

-   Every private resource must be scoped to the authenticated user or
    an explicitly authorized role.
-   Never rely on a user-supplied profile ID as proof of access.
-   Enforce authorization on the backend for every request.
-   Use secure session storage and revocation.
-   Apply rate limits to authentication, integration, and expensive
    operations.
-   Use CSRF protections if cookie-based browser flows are used.
-   Apply CORS narrowly to approved origins where relevant; do not treat
    CORS as authentication.

## 12.3 Secrets

-   No production credentials in source code, sample files, frontend
    bundles, or packaged desktop resources.
-   `.env.example` contains placeholders only.
-   Use a cloud secret manager or equivalent protected environment
    injection for backend secrets.
-   Encrypt third-party refresh/access tokens at rest and restrict
    decryption to the integration service.
-   Rotate credentials and provide revocation procedures.
-   Never log Authorization headers, cookies, access tokens, or full
    secret-bearing URLs.

## 12.4 Transport and storage

-   Enforce HTTPS in production.
-   Use managed encrypted database storage and encrypted backups.
-   Limit database network access.
-   Apply least-privilege database roles.
-   Separate production and non-production data.
-   Define retention and deletion policies.
-   Store only data needed for the product.

## 12.5 Desktop hardening

-   Use Tauri's capability/permission model with least privilege.
-   Avoid broad filesystem and shell permissions.
-   Validate any external navigation and deep links.
-   Protect the updater and signing keys.
-   Do not put private backend secrets in the client.
-   Validate data received from the backend.
-   Keep logs local and sanitized unless the user explicitly sends a
    diagnostic report.

## 12.6 Responsible assessment

-   Do not equate platform activity with overall ability or worth.
-   Do not label students as incapable or unemployable.
-   Do not imply causation from correlational features.
-   Avoid public comparisons and leaderboards by default.
-   Provide context for missing data and source bias.
-   Allow users to inspect and correct manual information.
-   Do not infer protected or sensitive traits.
-   Provide a route to report inaccurate data or misleading assessments.
-   Evaluate whether the product could unfairly disadvantage users with
    low platform activity, private repositories, accessibility
    constraints, or different learning paths.

## 12.7 Privacy and consent

Before production launch, provide: - Privacy policy. - Terms of use. -
Data-source disclosure. - Integration permission explanation. - Consent
for optional research/training use where required. - Data export and
deletion mechanism. - Support/contact route. - Retention schedule. -
Incident response process.

Legal review may be required depending on deployment jurisdiction, data
types, and audience.

------------------------------------------------------------------------

# 13. Non-Functional Requirements

Targets below are proposed acceptance goals. They must be measured and
adjusted based on deployment constraints; they are not claims about
current performance.

## 13.1 Performance

-   Desktop shell should become interactive quickly on a typical
    supported laptop; target a median cold start of under 3 seconds
    after installation, excluding network authentication and service
    latency.
-   Common API reads should target p95 under 500 ms under the agreed
    test load, excluding external-source calls and long-running jobs.
-   Long-running sync/training work must not block the UI or hold an
    HTTP request open indefinitely.
-   UI should show progress for operations that take more than a short,
    perceptible interval.
-   Database queries must be measured on representative data before
    adding speculative indexes.
-   External API calls must have bounded timeouts and retries.

## 13.2 Reliability

-   Define service-level objectives after deployment topology and
    expected traffic are known.
-   Backend failures must not corrupt prior assessment records.
-   A failed sync must not silently erase the last known good data.
-   A failed model deployment must leave the prior approved model
    active.
-   Jobs must have observable terminal states.
-   Database backups must be restorable through a tested procedure.

## 13.3 Scalability

The first release should prioritize correctness and operational
simplicity over premature distributed architecture.

The system should nevertheless support: - More than one concurrent
user. - Paginated API responses. - Connection pooling. - Bounded batch
sizes. - Rate-limited ingestion. - Indexes based on measured query
patterns. - Separation of training from online inference. - Background
jobs when workload requires them.

Capacity targets must be established from realistic load tests, not
guessed.

## 13.4 Accessibility

-   Keyboard-accessible navigation and forms.
-   Visible focus states.
-   Sufficient color contrast.
-   Text alternatives for meaningful charts.
-   Status indicators that do not rely on color alone.
-   Reasonable screen-reader labels for controls.
-   Clear error messages and validation feedback.

## 13.5 Maintainability

-   Strict TypeScript configuration.
-   Python formatting, linting, and type-checking strategy.
-   Unit, integration, API contract, and desktop end-to-end tests.
-   Architecture decision records for significant choices.
-   Documented environment setup.
-   Automated database migration checks.
-   Dependency updates and vulnerability review.
-   No large unreviewed rewrites.
-   Small, testable implementation steps.

## 13.6 Observability

-   Structured logs with request/correlation IDs.
-   Metrics for API latency, errors, sync success/failure, job duration,
    model version, and resource use.
-   Tracing if operational complexity warrants it.
-   Alerts for critical service failures.
-   PII-minimizing log fields.
-   Model/data-quality monitoring separated from infrastructure health.

## 13.7 Compatibility

Initial supported platform: - Windows 10/11, 64-bit, with a documented
minimum supported OS/build after testing.

Initial backend support: - A documented Python version and dependency
lock strategy. - A supported PostgreSQL version selected for managed
hosting and CI.

Other operating systems are future scope unless explicitly approved.

------------------------------------------------------------------------

# 14. API Contract Requirements

The existing API contains routes for health, students, ingestion,
features, predictions, insights, pipeline orchestration, ranking, and
administrative retraining. These provide useful functional reference
points but must be reviewed before public deployment.

## 14.1 API design principles

-   Use `/api/v1` or another deliberate versioning scheme.
-   Use UUID-like non-guessable public identifiers where appropriate,
    without treating unguessability as authorization.
-   Apply authorization at the service/resource boundary.
-   Return consistent error structures with stable machine-readable
    codes.
-   Validate all inputs.
-   Paginate collections.
-   Use UTC timestamps in ISO 8601 form.
-   Document nullable/missing fields.
-   Support idempotency for operations that may be retried.
-   Avoid exposing internal database IDs if they create coupling or
    enumeration risks.
-   Avoid synchronous work beyond a bounded request duration.
-   Publish an OpenAPI contract and test it in CI.

## 14.2 Candidate resource groups

Final paths and schemas are subject to API design review.

-   `/api/v1/auth/*` or identity-provider-managed auth flows.
-   `/api/v1/me`
-   `/api/v1/profile`
-   `/api/v1/integrations`
-   `/api/v1/integrations/{provider}/connect`
-   `/api/v1/integrations/{provider}/sync`
-   `/api/v1/sync-runs/{id}`
-   `/api/v1/assessments`
-   `/api/v1/assessments/{id}`
-   `/api/v1/assessments/{id}/evidence`
-   `/api/v1/assessments/{id}/recommendations`
-   `/api/v1/assessment-history`
-   `/api/v1/data-export`
-   `/api/v1/account/deletion`
-   `/api/v1/health/live`
-   `/api/v1/health/ready`

Do not copy these paths blindly. Use them as a starting contract for the
implementation design.

## 14.3 Error categories

At minimum, clients should be able to distinguish: - Authentication
required/expired. - Permission denied. - Resource not found. - Invalid
input. - Rate limit exceeded. - Integration unavailable. - Partial
sync. - Insufficient data. - Assessment unavailable. - Job still
running. - Service temporarily unavailable. - Unexpected internal
failure.

Error responses must not expose stack traces, SQL statements, secrets,
or raw third-party responses.

------------------------------------------------------------------------

# 15. Testing and Quality Strategy

## 15.1 Backend tests

-   Unit tests for feature definitions, rules, validators, and domain
    logic.
-   API contract tests.
-   Integration tests against a disposable PostgreSQL instance.
-   Migration tests from empty and supported prior schemas.
-   Authorization/tenant-isolation tests.
-   External API tests with mocked responses and rate-limit/failure
    cases.
-   Pipeline idempotency and partial-failure tests.
-   Model artifact loading and compatibility tests.
-   Candidate model promotion and rollback tests.
-   Data-deletion and retention behavior tests.

## 15.2 ML tests

-   Deterministic feature computation tests.
-   Label-generation tests where synthetic labels are intentionally
    used.
-   Leakage checks.
-   Train/inference feature schema parity.
-   Preprocessing fit-scope checks.
-   Baseline metric reproduction.
-   Artifact metadata and checksum verification.
-   Prediction range/schema tests where ranges are meaningful.
-   Out-of-distribution and missing-data behavior tests.
-   Regression tests for known failure cases.
-   No claim of model quality based solely on unit tests.

## 15.3 Desktop tests

-   UI unit/component tests.
-   API client and session tests.
-   Navigation and accessibility checks.
-   End-to-end onboarding.
-   Login/logout/session expiry.
-   Integration connection and sync.
-   Partial/failing sync.
-   Assessment and history.
-   Data export and account deletion.
-   Offline/backend outage behavior.
-   Installer install/upgrade/uninstall tests on clean Windows
    environments.

## 15.4 Security tests

-   Authorization boundary tests for every user-owned resource.
-   IDOR-style access attempts.
-   Token leakage checks in logs and packaged artifacts.
-   Dependency and secret scanning.
-   Input validation and injection tests.
-   Rate-limit tests.
-   Desktop permission/capability review.
-   Update/signature verification.
-   Backup access and restore checks.

## 15.5 CI gates

A pull request should not merge if required checks fail: -
Formatting/linting. - Type checks where configured. - Unit tests. -
Relevant integration tests. - Migration validation. - Frontend build. -
Desktop build smoke test where feasible. - Dependency/secret checks. -
ML evaluation contract checks for changes that affect training,
features, or inference.

A model change must include an evaluation report. A UI-only change does
not need to retrain the model.

------------------------------------------------------------------------

# 16. Release Acceptance Criteria

The first public production release is not ready until all P0 items
below are satisfied or explicitly deferred with an approved risk
decision.

## 16.1 Product

-   [ ] Installable Windows application.
-   [ ] Onboarding and authentication work.
-   [ ] User can view/edit their profile.
-   [ ] User can connect/disconnect supported integrations.
-   [ ] User can preview collected data and understand its provenance.
-   [ ] Sync status and errors are visible.
-   [ ] Assessment includes evidence and limitations.
-   [ ] Development recommendations are actionable and traceable.
-   [ ] Assessment history preserves historical snapshots.
-   [ ] Privacy controls and account deletion are available.
-   [ ] Demo data is unmistakably labelled.

## 16.2 Engineering

-   [ ] API is versioned and documented.
-   [ ] User authorization is enforced on the server.
-   [ ] Database migrations work on a clean environment.
-   [ ] No production secrets are embedded in the client or repository.
-   [ ] Critical flows have integration and end-to-end tests.
-   [ ] Error responses are safe and consistent.
-   [ ] Logs are structured and sanitized.
-   [ ] Backup/restore procedure is tested.
-   [ ] Installer signing and update strategy are documented.
-   [ ] CI covers backend and frontend, with desktop build checks.

## 16.3 ML and data integrity

-   [ ] Assessment target and semantics are documented.
-   [ ] Synthetic targets are not represented as real placement
    outcomes.
-   [ ] No fabricated source timestamps are used as observed behavior.
-   [ ] Feature definitions and missing-data behavior are versioned.
-   [ ] Data provenance is available for assessment inputs.
-   [ ] Baselines and evaluation methodology are documented.
-   [ ] Evaluation is leakage-safe.
-   [ ] Model artifact and feature-schema versions are recorded.
-   [ ] Candidate model validation and rollback are tested.
-   [ ] User-facing claims match the evidence.
-   [ ] Known limitations are visible in product documentation.

## 16.4 Operations

-   [ ] Staging deployment passes smoke tests.
-   [ ] Production configuration is separated from development.
-   [ ] Health and readiness checks work.
-   [ ] Monitoring and alerting exist for critical failures.
-   [ ] Incident response and credential rotation procedures exist.
-   [ ] Privacy policy and terms are published.
-   [ ] Support/contact route is available.

------------------------------------------------------------------------

# 17. Metrics and Success Criteria

Do not optimize only for downloads, model accuracy, or time spent in the
application.

## 17.1 Product metrics

Candidate metrics: - Installer download-to-successful-launch rate. -
Onboarding completion rate. - Percentage of users who successfully
connect at least one source. - Successful sync rate. - Percentage of
assessments with sufficient data. - Percentage of users who view
evidence or feature explanations. - Recommendation usefulness
feedback. - User return rate over a defined period. - Account deletion
and support-request rates.

Collect only what is necessary, disclose analytics, and avoid
unnecessary behavioral surveillance.

## 17.2 Engineering metrics

-   API availability and error rate.
-   p50/p95/p99 latency for key endpoints.
-   Sync success/failure rate by source.
-   Background job failure and retry rate.
-   Database query latency.
-   Desktop crash rate where reliable privacy-respecting telemetry is
    enabled.
-   Installer/update failure rate.
-   Mean time to detect and recover from critical incidents.

## 17.3 ML metrics

Metrics depend on the final research target. Possible measures
include: - Baseline-relative predictive performance. - Precision/recall
or error metrics appropriate to the task. - Calibration error when
probabilities are produced. - Error by relevant, ethically and
statistically supportable subgroups. - Robustness under missingness or
distribution shift. - Inference latency and resource cost. - Rate of
assessments withheld for insufficient evidence. - Stability of
explanations where relevant.

**Do not set an arbitrary "95% accuracy" target before defining the
target and dataset.** A metric threshold must be justified by the task,
baseline, uncertainty, and practical cost of errors.

------------------------------------------------------------------------

# 18. Risks and Mitigations

  -----------------------------------------------------------------------
  Risk                    Impact                  Mitigation
  ----------------------- ----------------------- -----------------------
  No trustworthy          Product cannot          Begin with transparent
  placement-outcome       substantiate placement  preparation
  labels                  prediction              intelligence or obtain
                                                  valid labelled data

  Platform APIs change or Ingestion breaks        Isolate adapters, test
  restrict access                                 failures, monitor
                                                  contracts, provide
                                                  graceful
                                                  disconnect/manual
                                                  alternatives

  Activity metrics        Misleading assessment   Explain limitations,
  misrepresent ability                            avoid overclaiming,
                                                  validate feature
                                                  utility

  Synthetic data          Inflated/invalid        Provenance labels,
  contaminates evaluation metrics                 separate fixtures,
                                                  dataset checks

  Data leakage inflates   False confidence        Temporal/group-aware
  ML results                                      splits, leakage audits,
                                                  isolated test data

  Desktop client leaks    Account compromise      No embedded backend
  secrets                                         secrets, secure session
                                                  storage, artifact scans

  User data leaks across  Severe privacy breach   Server-side ownership
  accounts                                        enforcement and
                                                  adversarial
                                                  authorization tests

  External integration    Poor sync reliability   Caching, backoff,
  rate limits                                     bounded retries,
                                                  visible sync status

  Model update breaks     Incorrect or            Versioned bundles,
  inference               unavailable assessments smoke tests, atomic
                                                  activation, rollback

  Cloud cost grows        Service disruption or   Budget alerts, usage
  unexpectedly            unsustainable operation limits, resource
                                                  monitoring, avoid
                                                  premature
                                                  infrastructure

  Desktop update/install  Users cannot launch or  Signed artifacts,
  failure                 update                  staged rollout,
                                                  rollback and
                                                  clean-machine tests

  Recommendations are     Low trust/retention     Evidence-linked
  generic or unhelpful                            actions, user feedback,
                                                  measured iteration

  Sensitive educational   Privacy and trust harm  Data minimization,
  data is over-collected                          consent,
                                                  retention/deletion
                                                  policies, review

  Scope expands           Project stalls          Release gates, P0/P1/P2
  excessively                                     prioritization,
                                                  evidence-based
                                                  additions
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 19. Open Decisions

These decisions require explicit resolution. Do not silently assume
answers in implementation.

1.  **Initial assessment target:** Actual placement-related outcome, or
    preparation assessment until valid outcome data is available?
2.  **Identity mechanism:** Managed identity provider, email
    verification, or another approach?
3.  **GitHub access:** Public profile-only integration, delegated
    authorization, or both?
4.  **LeetCode source:** Is the intended data interface stable,
    permitted, and sufficient for the required feature semantics?
5.  **CGPA and academic data:** Which fields are genuinely necessary and
    optional?
6.  **Cloud provider:** Which provider offers the best combination of
    cost, managed PostgreSQL, secret management, backups, and deployment
    simplicity?
7.  **Background jobs:** At what measured workload should a worker/queue
    be introduced?
8.  **Model artifact storage:** Local deployment artifact, object
    storage, or a dedicated registry?
9.  **Desktop updater:** Which secure signing and update mechanism will
    be used?
10. **Analytics:** Which minimal, disclosed product analytics are
    acceptable?
11. **Report export:** PDF, CSV, or both in the first release?
12. **Offline mode:** Is there sufficient user demand to justify local
    model execution and local storage?
13. **Institutional/cohort use:** Is this strictly personal-use software
    initially, or is there a future authorized institutional deployment?
14. **Research participation:** Will any user data be used for research
    beyond generating that user's assessment? If yes, define separate
    consent and governance.
15. **Public release/licensing:** Confirm repository license
    compatibility, third-party license obligations, and the intended
    distribution model.

The first architecture/research milestone must resolve decisions 1, 3,
4, and 6 sufficiently to unblock safe implementation.

------------------------------------------------------------------------

# 20. Recommended Repository Evolution

The repository should evolve incrementally. The following is a proposed
direction, not a requirement to move every file at once.

``` text
PIS/
├── apps/
│   └── desktop/
│       ├── src/
│       │   ├── app/
│       │   ├── components/
│       │   ├── features/
│       │   ├── lib/
│       │   └── styles/
│       ├── src-tauri/
│       ├── tests/
│       ├── package.json
│       └── ...
├── app/
│   ├── main.py
│   ├── routers/
│   ├── schemas/
│   └── ...
├── domain/
│   ├── profiles/
│   ├── provenance/
│   ├── features/
│   ├── assessments/
│   └── recommendations/
├── services/
│   ├── ingestion/
│   ├── assessment/
│   ├── sync/
│   └── ...
├── ingest/
├── features/
├── ml/
│   ├── training/
│   ├── evaluation/
│   ├── inference/
│   └── ...
├── insights/
├── persistence/
│   ├── models/
│   ├── repositories/
│   └── migrations/
├── experiments/
│   ├── configs/
│   ├── reports/
│   └── ...
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── ml/
├── docs/
│   ├── PRD.md
│   ├── architecture/
│   ├── research/
│   ├── data-dictionary/
│   ├── model-cards/
│   ├── security/
│   └── runbooks/
├── infra/
│   ├── deployment/
│   └── ...
├── docker-compose.yml
├── Makefile
└── README.md
```

Guidance: - Do not create empty folders solely to match this tree. -
Move code only when the move improves a clear boundary or supports an
immediate requirement. - Keep current local Docker development available
for contributors. - The production desktop client must not require
Docker. - Keep training and evaluation code out of the latency-sensitive
API startup path. - Keep model artifacts and user data out of version
control unless a specific, safe, documented fixture is required. - Keep
generated secrets and environment files out of the repository.

------------------------------------------------------------------------

# 21. Implementation Work Breakdown

## Epic A --- Baseline reproducibility

-   A1. Document and reproduce current local startup.
-   A2. Run current unit tests.
-   A3. Run integration tests against PostgreSQL.
-   A4. Audit database schema and migrations.
-   A5. Audit source-data semantics.
-   A6. Establish CI and quality gates.

## Epic B --- Product and research definition

-   B1. Write target-definition and intended-use document.
-   B2. Inventory available data sources and their limitations.
-   B3. Conduct focused literature/competitor review.
-   B4. Select initial research question.
-   B5. Define baseline and evaluation protocol.
-   B6. Write initial data dictionary and model card template.

## Epic C --- Secure backend foundation

-   C1. Define user identity and ownership model.
-   C2. Add authentication integration.
-   C3. Add server-side authorization tests.
-   C4. Define API v1 contracts.
-   C5. Implement migrations and provenance model.
-   C6. Add sync-run records and safe error states.
-   C7. Add secure secret/token handling.
-   C8. Implement data export/deletion lifecycle.

## Epic D --- ML and assessment reliability

-   D1. Replace or isolate synthetic target behavior.
-   D2. Define versioned feature schema.
-   D3. Fix feature/inference preprocessing parity.
-   D4. Implement baseline evaluation.
-   D5. Implement leakage-safe experiment runner.
-   D6. Add model metadata and artifact checksums.
-   D7. Implement candidate model validation.
-   D8. Implement safe model activation/rollback.
-   D9. Generate model/evaluation reports.
-   D10. Add assessment snapshot provenance.

## Epic E --- Desktop foundation

-   E1. Scaffold Tauri + React + TypeScript.
-   E2. Define visual tokens and navigation.
-   E3. Implement API client and auth/session handling.
-   E4. Implement onboarding.
-   E5. Implement profile and integrations screens.
-   E6. Implement sync and error states.
-   E7. Implement assessment overview and evidence.
-   E8. Implement development plan.
-   E9. Implement history and comparison.
-   E10. Implement privacy/settings controls.
-   E11. Add UI and end-to-end tests.

## Epic F --- Distribution and operations

-   F1. Configure Windows application metadata and icon.
-   F2. Configure signing and secure updates.
-   F3. Build installer in CI.
-   F4. Test install/upgrade/uninstall on clean machines.
-   F5. Deploy staging backend.
-   F6. Configure production secrets and managed database.
-   F7. Configure monitoring, alerts, and backups.
-   F8. Conduct security and privacy review.
-   F9. Publish user documentation, privacy policy, and terms.
-   F10. Run release acceptance checklist.

Dependencies: - Do not begin full desktop integration against unstable
API contracts. - Do not build outcome-prediction UX before target
semantics and evaluation are approved. - Do not enable real-user
ingestion before ownership isolation and secret handling are tested. -
Do not publish a model-performance claim before its experiment is
reproducible.

------------------------------------------------------------------------

# 22. Documentation Deliverables

The product should maintain the following living documents:

-   Product requirements document (this document).
-   Architecture decision records.
-   API/OpenAPI documentation.
-   Data dictionary and feature definitions.
-   Data provenance and retention policy.
-   Integration behavior/limitations.
-   Research question and experiment protocol.
-   Model cards.
-   Dataset documentation.
-   Threat model and security review.
-   Privacy policy and terms.
-   Database migration/runbook.
-   Deployment and rollback runbook.
-   Backup/restore runbook.
-   Incident response and credential rotation runbook.
-   Desktop installation/update/troubleshooting guide.
-   Release notes and known limitations.

Documents must reflect implemented behavior. Do not describe planned
functionality as already available.

------------------------------------------------------------------------

# 23. Definition of Done

A feature is not done merely because it appears to work on the
developer's machine.

A production-facing feature is done when: 1. Its behavior and acceptance
criteria are documented. 2. Inputs and permissions are validated on the
backend. 3. Loading, empty, partial, and error states are handled. 4.
Relevant unit and integration tests pass. 5. Security and privacy
implications have been reviewed. 6. Logs and diagnostics are safe. 7.
API and data-model changes are migrated and documented. 8. The UI
communicates data limitations accurately. 9. Existing supported flows
remain functional. 10. The implementation has been reviewed and can be
reproduced.

An ML change additionally requires: 1. A clear hypothesis or justified
modeling change. 2. A documented baseline. 3. A reproducible evaluation.
4. Leakage checks. 5. Error analysis. 6. Artifact/version metadata. 7. A
clear decision about whether the change merits adoption.

A release is done only when the release acceptance checklist passes or
every exception has an explicit owner, rationale, and risk acceptance.

------------------------------------------------------------------------

# 24. Immediate Next Steps

Do these in order.

1.  **Freeze the product direction:** Cloud-connected Windows desktop;
    Tauri + React + TypeScript client; FastAPI/Python backend; managed
    PostgreSQL.
2.  **Audit and stabilize the current repository:** database
    initialization, migrations, ingestion semantics, model loading,
    tests, configuration, and security boundaries.
3.  **Resolve the research target:** determine whether credible outcome
    labels are available. If not, define the initial product as
    preparation intelligence and select a defensible narrower ML
    problem.
4.  **Write architecture decisions:** identity, GitHub connection model,
    LeetCode feasibility, cloud provider, migrations, secrets, and
    updater.
5.  **Define API v1 and data ownership:** do this before coupling the
    desktop UI to backend implementation details.
6.  **Implement the secure backend foundation and data provenance.**
7.  **Build the first desktop vertical slice:** launch app →
    authenticate → load profile → show API health and integration state.
8.  **Add sync, assessment, evidence, recommendations, and history in
    tested increments.**
9.  **Package and test on a clean Windows environment.**
10. **Publish only claims supported by the completed ML evaluation.**

## Final product statement

PIS will be a cloud-connected Windows desktop application that helps
students inspect their development evidence, understand a transparent
preparation assessment, and act on prioritized recommendations. Its
Python backend will manage data ingestion, feature computation, ML
inference, and versioned assessments. The project will pursue advanced
ML methods only through a documented research process with valid data,
appropriate baselines, reproducible evaluation, and explicit
limitations.

**The governing rule is simple: build a product users can trust, and
make every claim earn that trust.**
