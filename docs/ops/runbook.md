# Staging / Production Runbook (AWS)

> **Future:** the AWS deployment described here has not been run against a real account. **Owner decision 10 (2026-10-24): infrastructure budget is $0/month.** AWS is used only if the whole setup can be proven free; the ALB, RDS and NAT below are not. Hosting is chosen in Phase 7.2 after a free-host comparison. The sections below describe the AWS option and stay as written.

Status legend: **[done: local]** rehearsed on a local scratch database or container, **[done]** verified by a test, **[unverified]** written but never executed, **[todo]** requires a real hosting account. Nothing in this file has been executed against a cloud account.

## 1. Environments
| | local | test | staging | production |
|---|---|---|---|---|
| `APP_ENV` | local | test | staging | production |
| DB | compose `db` | throwaway DB | own RDS | own RDS (Multi-AZ, deletion-protected) |
| Seed data | yes | yes | **refused** | **refused** |
| Entry | `entrypoint.sh` trains + seeds | pytest | uvicorn only | uvicorn only |
| Secrets | `.env` | env | Secrets Manager `pis-staging/*` | Secrets Manager `pis-production/*` |

`config.validate()` already refuses staging/production without `AUTH_*` or with placeholder DB URLs; `entrypoint.sh` skips migrate/train/seed there. **[done]** (unit-tested config; entrypoint branch not executed in a container)

Staging and production must use different DB instances, secrets, IdP audience and, ideally, separate AWS accounts. Production console/CLI access: SSO role, MFA, no long-lived keys. **[todo]**

## 2. First-time setup **[todo]**
1. Create ECR repo `pis-api`, an S3 state bucket + lock table, ACM certificate, VPC with private/public subnets.
2. `cd deploy/aws && terraform init -backend-config=<env>.backend.hcl && terraform validate && terraform plan -var-file=<env>.tfvars` (tfvars/backends are not committed).
3. Apply. Then set secrets out-of-band (never in tfvars/state):
   - Create a DB role for the app (see §6), then
     `aws secretsmanager put-secret-value --secret-id pis-<env>/DATABASE_URL --secret-string "postgresql://..."` (use `?sslmode=require`).
   - `aws secretsmanager put-secret-value --secret-id pis-<env>/GITHUB_TOKEN --secret-string "<token or empty>"`.
4. Confirm the SNS email subscription.

## 3. Release (controlled, immutable) **[unverified]**
`PRIVATE_SUBNET=… APP_SG=… deploy/aws/release.sh <env> <region> <ecr-uri>`
Flow: clean-tree check → build image tagged by git SHA → push → register migrate task → run migration as one-off Fargate task → abort service update if exit code ≠ 0 → roll service → wait for stable. ECS circuit breaker auto-rolls back if new tasks fail `/health/ready`.

**Model bundles:** staging/production do not require a model. Real-user assessments never use it, so startup and `/health/ready` need only valid config, a reachable DB and applied migrations; `/health/detailed` reports `model_version: "none"` when no bundle is active. Local/test still fail fast without a verified active bundle (`ml/bundle.py`). Bundles are not in the image (`.dockerignore`); promote one only as an operator action against the target DB (`python -m ml.bundle approve/activate`). **[unverified: Docker not run]**

Probes: ALB → `/health/ready` (DB + migrations applied, 503 otherwise; local also needs an active model); container → `/health`.
Sizing: API 0.5 vCPU / 1 GB, 1 task staging / 2 production; stop timeout 30 s. Tune after load measurement (not done).

## 4. Rollback **[todo — rehearse in staging]**
- App: `release.sh <env> <region> <ecr-uri> <previous-sha>` re-points the service at the prior image. Migrations stay applied, so every migration must be backward-compatible with the previous release (add-only; drop columns in a later release).
- Bad model: `python -m ml.bundle activate <previous-version> --by <you>` (no redeploy needed if the bundle is in the image).
- Bad schema: restore (§6); there are no down-migrations.

## 5. Observability
- Logs: JSON lines in staging/production (`app/logger.py`) with `request_id`, method, path, status, `duration_ms`; `X-Request-ID` echoed to callers; CloudWatch group `/pis/<env>`, 30-day retention. **[done]** (formatter unit-tested)
- Sync: each sync emits `msg=sync_finished` with `run_id`, `sync_status`, `error_code`; metric filter + alarm at >5 failures/15 min. **[unverified]**
- Model version: reported by `/health/detailed` and stored with predictions/assessments (`model_version`). **[done, pre-existing]**
- Alarms (SNS email): no healthy targets, 5xx > 10/5 min, p95 latency > 2 s, DB connections > 60, free storage < 3 GB, sync failures, RDS backup/failure events, monthly budget 80 %. **[unverified]**
- Not built: per-job duration metric (derive from `sync_runs.started_at/completed_at` for now), dashboards, paging beyond email.

## 6. Database access, backups, restore
- **Least privilege gap:** the migrate task and API currently share one `DATABASE_URL` secret, so the app role must be able to run DDL. Splitting into a migration role (DDL) and an app role (DML only) needs a separate `MIGRATE_DATABASE_URL` in `ingest/migrate.py`. Not implemented. Until then use a dedicated non-superuser role (not the RDS master) for `DATABASE_URL`. **[open]**
- Backups: automated, encrypted, 14-day PITR, 02:00–03:00 UTC window; production keeps a final snapshot. **[unverified]** The 14 days is inside the 35-day ceiling in `docs/data/privacy-and-retention.md`.
- **Local dump/restore rehearsal [done: local], 2026-10-24** (scratch Postgres 15 container, never a real database): `python -m ingest.migrate --seed` into `rehearse`, then `pg_dump -Fc -d rehearse -f rehearse.dump`, `createdb rehearse_restored`, `pg_restore --no-owner -d rehearse_restored rehearse.dump`. Row counts compared with one `select ... count(*)` per table (students 8, users 1, coding_activity 79, github_activity 23, features 0, schema_migrations 11, assessments 0): identical. Note: a pg_dump 18 client against a 15 server wrote `SET transaction_timeout`, which a 15 server rejects on restore (one harmless error, all data restored); use a `pg_dump` of the server's major version. This proves the procedure on a local database only, not a managed service, PITR or RTO.
- Targets (proposed, owner to confirm): RPO ≤ 5 min (PITR), RTO ≤ 4 h.
- **Restore drill [todo]:** `aws rds restore-db-instance-to-point-in-time` into a new instance → point a scratch task at it → `python -m ingest.migrate` reports nothing pending → `/health/ready` 200 and a profile read works → record date, duration, and row counts here. No evidence exists yet.

## 7. Credential rotation
- DB password / app role: create new password → `put-secret-value` → `aws ecs update-service --force-new-deployment` → verify `/health/ready` → revoke old.
- GitHub token: same flow. IdP signing keys rotate via JWKS automatically (RS256).
- Rotate immediately on any suspected leak; never print values.

## 8. Incident response
1. Page/alert → check `/health/ready`, ECS service events, `/pis/<env>` logs by `request_id`.
2. Bad release → rollback (§4). Data issue → stop sync (disable GitHub token secret value / scale to 0), snapshot, assess, restore if needed.
3. Suspected data exposure: scale service to 0, rotate secrets, preserve logs, follow privacy obligations in `docs/data/privacy-and-retention.md`, write a post-incident note in `docs/`.

## 9. Staging acceptance (§15.6) **[todo]**
Using synthetic/test accounts only, against the deployed staging URL: sign-in via staging IdP → create profile → connect GitHub test user → sync → assessment → export → delete account; plus unauth/forbidden checks (401/403), `/health/ready`, a forced bad release to prove auto-rollback. `tests/test_api_v1.py` can be pointed at a DB-backed local stack but has not been run against AWS.

## 10. GitHub calendar collection: rate budget and pilot
Default is off. In staging/production it needs `GITHUB_CALENDAR_ENABLED=true` **and** `GITHUB_CALENDAR_APPROVED=true` (config refuses to start otherwise), plus a server `GITHUB_TOKEN`.

**Rate budget (from code; the 5000/h limit is from `docs/research/github-calendar-spike.md`, other figures are derived, not measured under load).**
- Per sync: 1 GraphQL call (spike: cost 1) + REST: 1-3 repo-list pages (`_MAX_PAGES=3`, usually 1) + at most `MAX_REPOS=10` commit-count calls. Typical ≈ 12 REST + 1 GraphQL; worst case 13 REST + 1 GraphQL.
- Assumptions: token has 5000 REST/h and 5000 GraphQL/h as separate buckets (spike showed `X-RateLimit-Resource: graphql`; the REST bucket is GitHub's documented default, not re-checked); retries on 5xx (up to 3 attempts per call) are ignored and add cost; one shared token for all users; the limit is per token, not per user.
- Cooldown: `SYNC_COOLDOWN_SECONDS=300` per connection, so one user costs at most 12 syncs/h ≈ 156 REST calls/h.
- Capacity: REST is the bottleneck. 5000 / 13 ≈ 380 syncs/h; at the cooldown cap that is ≈ 32 users syncing continuously, far more at normal use (one sync per user per day ≈ 380 users/h in a burst). The API limiter state is per process, so more than one replica multiplies the real call rate; stay at one replica during the pilot.
- On `rate_limited` the run is `failed` or `partial`; watch the `sync_status=failed` alert (§5).

**Consent text:** `apps/desktop/src/screens/Privacy.tsx` was compared with `ml/forecast/export.py`: daily counts only, consent checked at export time, per-export random salt (codes not linkable across exports), past files cannot be recalled. The wording matches; no change made. **Needs owner/legal review** before any real volunteer beyond the owner.

## 11. Manual pilot procedure (dev environment only)
1. Dev environment only (`APP_ENV=local` or a dev stack); never staging/production in this phase. Set `GITHUB_TOKEN` (never print it), `GITHUB_CALENDAR_ENABLED=true`.
2. Own account first: sign in, create profile, connect your own public GitHub username, sync, check the run is `succeeded`/`partial` and `github_contribution_day` rows exist with `provenance=observed`. Do not turn on research consent until you have read the Privacy screen text.
3. Volunteers only after the consent text is reviewed by the owner/legal. Each volunteer must explicitly agree beforehand (written); no one's data is collected without it. They connect their own username themselves.
4. Research export only for users with consent set: `python -m ml.forecast.export --out <dir> --i-understand-this-exports-research-data`. Keep files outside the repo; they cannot be recalled.
5. Stop: disconnect with data deletion or delete the account; set the flag back to `false`.

## 12. Local preparation results (Phase 7.1, 2026-10-24)
No AWS credentials were used and no AWS, ECR or registry call was made.
- Terraform 1.9 (Docker image `hashicorp/terraform:1.9`, provider download only): `fmt` applied (whitespace in 4 lines of `main.tf`); `init -backend=false` and `validate` on a scratch copy: **"Success! The configuration is valid."** **[done: local]** `plan` was not run (needs variables and credentials).
- `deploy/aws/release.sh`: added `--dry-run` (prints every step, runs no docker/terraform/aws; git is read only) and removed the `models/bundles` pre-check, which contradicted Phase 1.1 (deployed environments need no model). Checked: `sh -n` passes; a dirty tree aborts with exit 1; a dry run with an explicit tag prints the plan and exits 0. Migration failure aborts by reading (`[ "$CODE" = "0" ] || ... exit 1`, set -eu); not executed. `shellcheck` is not installed (not run). **[done: local]** for dry-run and abort, **[unverified]** for the real release.
- Review of `main.tf`: HTTPS listener takes `certificate_arn`; target group health path `/health/ready`; RDS `publicly_accessible = false`, Multi-AZ and deletion protection only for production, 14-day backups; DB URL and GitHub token come from Secrets Manager (the `?sslmode=require` instruction is in §2); log retention 30 days; seven alarms plus an SNS subscription and a budget; desired count 1 (staging) / 2 (production); task 512 CPU / 1024 MB. The VPC, subnets and NAT are inputs, not resources of this file. Under the $0 decision these are all chargeable except possibly parts of an account's free tier: **cost drivers** are the ALB (hourly + LCU), Fargate vCPU/GB-hours, RDS instance + storage + backups, NAT gateway (hourly + data) or its alternatives, Secrets Manager (per secret), CloudWatch logs/alarms, ECR storage, data transfer. AWS Pricing Calculator inputs would be: region, task count and size, hours per month, RDS class/storage/Multi-AZ, NAT count and GB processed, ALB LCUs, secrets count, log GB. No prices are stated here.
- Logging: tests added (`tests/test_ops.py`): the `X-Request-ID` appears in logs and the 500 envelope, and a bearer token never appears in log records. Known: unhandled errors log the exception message (`app/main.py`), which could contain driver text; it is not returned to callers. **[done]**
