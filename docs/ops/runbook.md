# Staging / Production Runbook (AWS)

> **Future:** the AWS deployment described here has not been run against a real account.

Status legend: **[done]** verified locally, **[unverified]** written but never executed, **[todo]** requires a real AWS account.

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

**Model bundles:** the API refuses to start without a verified active bundle (`ml/bundle.py`). The image must contain `models/bundles/<version>/` for a bundle already approved/activated in that environment's `model_versions` table. Training at boot is disabled in deployed envs. Promote with `python -m ml.bundle approve/activate` against the target DB as an operator action, before the release. The first-ever deploy to a fresh DB therefore needs: migrate → activate bundle → roll service. **[todo — not rehearsed]**

Probes: ALB → `/health/ready` (DB + migrations applied + active model, 503 otherwise); container → `/health`.
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
- Backups: automated, encrypted, 14-day PITR, 02:00–03:00 UTC window; production keeps a final snapshot. **[unverified]**
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
