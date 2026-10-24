# NexGauge documentation

Docs describe the repository as it is. Start with [architecture/current-state.md](architecture/current-state.md). Historical material is under `history/` and `product/` and may be out of date.

| Area | Document | What it covers |
|---|---|---|
| Architecture | [current-state](architecture/current-state.md) | verified description of the system, limits |
| | [api-surface](architecture/api-surface.md) | route table (checked by a test) |
| | [api-v1](architecture/api-v1.md) | `/api/v1` behaviour |
| | [domain-model](architecture/domain-model.md), [erd](architecture/erd.png), [draft-schema](architecture/draft-schema.sql) | entities, identity, provenance (design reference) |
| | [intelligence-spec](architecture/intelligence-spec.md) | draft intelligence and evaluation specification (unvalidated) |
| | [decisions/](architecture/decisions/) | ADRs 0001-0005 |
| | [query-optimization](architecture/query-optimization.md) | index/EXPLAIN results |
| Data | [data-dictionary](data/data-dictionary.md) | feature contract `features-v1` |
| | [provenance](data/provenance.md) | ingestion, provenance, data quality |
| | [privacy-and-retention](data/privacy-and-retention.md) | export, deletion, retention, audit |
| ML | [target](ml/target.md) | what the score means and does not mean |
| | [dataset-card](ml/dataset-card.md) | demo dataset |
| | [experiment-protocol](ml/experiment-protocol.md) | runner (implemented) and proposed RQ (not approved) |
| | [baseline-report](ml/baseline-report.md) | synthetic smoke-test results |
| | [forecast-report](ml/forecast-report.md) | RQ1 forecast pipeline; not run on real data |
| | [model-lifecycle](ml/model-lifecycle.md) | bundles, registry, assessments, rollback |
| Security | [auth-architecture](security/auth-architecture.md) | token verification, roles |
| | [desktop-session](security/desktop-session.md) | OIDC + PKCE sign-in |
| | [hardening](security/hardening.md) | partial hardening report |
| Ops (**future**: nothing here has run against real infrastructure) | [runbook](ops/runbook.md) | AWS staging/production runbook |
| Ops | [free-hosting](ops/free-hosting.md), [pilot-plan](ops/release/pilot-plan.md) | $0 hosting comparison; pilot kit (drafts) |
| | [release/](ops/release/) | installer, signing, release notes, clean-machine matrix |
| Research | [literature-and-competitors](research/literature-and-competitors.md), [data-source-feasibility](research/data-source-feasibility.md) | background |
| Design | [desktop](design/desktop.md) | desktop shell. No separate design-system document exists yet |
| Product | [PIS_PRD](product/PIS_PRD.md) | product spec; open decisions in §19 |
| History | [history/](history/) | baseline report, defect register, stabilization notes from earlier work |
