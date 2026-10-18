# ADR 0004 — Hosting: AWS (ECS Fargate + RDS PostgreSQL)

Status: accepted (owner decision, hosting work). Region, budget and account IDs are **not yet decided** — see Open items.

## Context
Backend = FastAPI container + PostgreSQL 15 (psycopg2). Needs: managed Postgres 15, secret store, private DB networking, PITR backups, logs/alarms, rollback, budget alerts (plan §15.1).

## Options considered
| | Render/Fly + managed PG | **AWS ECS Fargate + RDS** | GCP Cloud Run + Cloud SQL | Azure Container Apps + Flexible PG |
|---|---|---|---|---|
| PG 15 | yes | yes (`engine_version = 15`) | yes | yes |
| Secrets | env vars | Secrets Manager injected into the task | Secret Manager | Key Vault |
| Network control | limited | VPC, SG-only DB access, no public DB | VPC connector | VNet |
| Backups | daily | automated + PITR (14 d), snapshots | PITR | PITR |
| Alerts | basic | CloudWatch alarms, log metric filters, Budgets | Cloud Monitoring | Azure Monitor |
| Rollback | redeploy | ECS circuit breaker + prior task definition/image tag | revisions | revisions |
| Cost/effort | lowest | highest of the four (ALB + NAT + Multi-AZ prod) | moderate | moderate |

## Decision
AWS. Chosen for network isolation (private DB reachable only from the app security group), native secret injection without secrets in images/state, PITR, and alarm/budget tooling already needed by the plan. Trade-off accepted: more setup and a higher fixed cost (ALB, NAT, Multi-AZ in production) than a PaaS.

## Consequences
- Infra in `deploy/aws/main.tf`; release flow in `deploy/aws/release.sh`; ops in `docs/ops/runbook.md`.
- Images are immutable and tagged by git SHA; staging and production use separate stacks, DBs, secrets and IdP audience.
- Migrations are forward-only; rollback of the app does not roll back the schema (new migrations must be backward-compatible with the previous release).
- Terraform here has **not** been validated or applied.

## Open items (need an owner decision before first apply)
1. Region / data residency (student data; privacy policy in `docs/data/privacy-and-retention.md`).
2. Monthly budget per environment (`monthly_budget_usd`).
3. Production IdP issuer/audience/JWKS (the IdP vendor was left open).
4. Whether Multi-AZ production is worth the cost at launch scale.
