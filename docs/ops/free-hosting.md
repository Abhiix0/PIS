# Free hosting comparison ($0 budget)

Owner decision 10 (2026-10-24): infrastructure spend is **$0/month**, free services only, no promotional credits counted as free, no paid account upgrade. Researched 2026-10-24 from vendor pages and third-party summaries (links at the end). Free-tier terms change often and some sources disagree: every row marked *unverified* must be re-read on the vendor's own page before use. **Nothing here was deployed, and no account was created.**

## What NexGauge needs
- FastAPI container (python:3.11-slim image, uvicorn, one process) reachable over HTTPS by the desktop app.
- PostgreSQL 15-compatible database via `psycopg2` with `sslmode=require`, one `ThreadedConnectionPool`. Data is small (kilobytes per user).
- Runs without the owner's computer. Tolerates a slow first request. Background sync runs in-process for seconds.
- Auth is verified against an external IdP's JWKS, so the host needs outbound HTTPS only.
- Limits that matter: sleep and cold start, DB persistence and expiry, storage, monthly quotas, region, whether a card is required, and whether any usage can turn into a charge.

## Options

| Option | Fit | Findings (source) | Problem for NexGauge |
|---|---|---|---|
| **AWS** (ECS Fargate + ALB + RDS, existing Terraform) | Works technically | The stack's cost drivers (ALB, RDS, NAT, Fargate, Secrets Manager) are all metered. No always-free combination covers them | **Excluded.** Not provably $0 |
| **Render** web service (Free) | Container or native Python | Spins down after 15 min without traffic; 750 free instance hours per workspace per month, all free services suspended if exhausted (Render docs) | Cold start on the first request after idle. Card requirement *unverified* |
| **Render** Postgres (Free) | PG | Expires 30 days after creation, 14-day grace, then deleted; one per workspace (Render docs) | **Excluded**: data loss by design |
| **Neon** Postgres (Free) | PG, `sslmode=require` | 0.5 GB per project, 100 CU-hours per project per month, scale to zero after 5 min idle, 5 GB transfer; compute suspends when monthly limits are hit (Neon pricing/FAQ) | First query after idle wakes the compute; pooled connections go stale (see code note). No expiry stated |
| **Supabase** Postgres (Free) | PG | 500 MB, project **pauses after 7 days idle**, 2 active projects (third-party, *unverified*) | Pause needs a manual restore unless a keep-alive job runs |
| **Koyeb** | Container + PG | Sources conflict on whether a free web service still exists; free Postgres 1 GB with ~5 compute hours/month; a card with a $29 hold is reported; acquired by Mistral AI, Feb 2026 (third-party) | **Unverified**, card reported. Not relied on |
| **Oracle Cloud Always Free** VM | Full control (Docker + Postgres on one VM) | Ampere A1 allowance is disputed (4 OCPU/24 GB vs a reported cut to 2 OCPU/12 GB from 2026-06-15); over-allowance instances are disabled then deleted; card verification hold; "out of capacity" errors; idle instances may be reclaimed (third-party, *unverified*) | Card required; I would own patching, backups and uptime |
| **Google Cloud Run** | Container | 2M requests, 180k vCPU-s, 360k GiB-s free per month (Google pricing page) | A billing account is required (confirmed only for Cloud Functions 1st gen); usage beyond the free tier is billed. Conflicts with "no paid services" unless the owner accepts a card on file |
| Fly.io, Railway, Heroku | n/a | Not researched; free tiers are trials or paid | Not considered |

## Recommendation: best zero-cost compromise
**Render free web service (API) + Neon free Postgres (data) + a free OIDC IdP.** It is the only combination in this list that is documented as free, needs no VM administration, runs without the owner's computer, and keeps data past 30 days. Render's own free Postgres is rejected because it expires.

Accepted limitations, to be shown to users and the owner:
1. **Cold start.** After 15 idle minutes the API sleeps; the first request can take tens of seconds (duration not measured). The desktop already shows "loading" and error-with-retry states; `/health` polling would itself keep the service awake only while the app is open.
2. **Monthly quotas.** 750 instance hours and 100 CU-hours can run out; the service or compute then suspends until the next month. Fine for a pilot of a few users, not for public release.
3. **Storage cap** 0.5 GB: ample for the data model, no backups beyond what Neon provides (retention window *unverified*); `pg_dump` from the owner's machine is the backup plan.
4. **Single process**, so the per-process rate limit is effectively global, which suits one instance.
5. **Region is OPEN** (decision 9): available regions of both vendors were not verified. Student data residency (`docs/data/privacy-and-retention.md`) must be reviewed before choosing.
6. Terms may change; re-read them before signing up and at each pilot start.

## Code follow-ups this choice needs
- Done (2026-10-24): `ingest/db_connection.py` checks a pooled connection with `SELECT 1` on checkout and replaces a dead one (unit-tested with a fake pool; not tested against a real suspended Neon compute).
- A free container host builds from the repository's `Dockerfile`; migrations run as a pre-deploy command or one-off job using `python -m ingest.migrate` (no model needed, Phase 1.1).
- `AUTH_*` and `CORS_ALLOWED_ORIGINS` (desktop origin) are set as host environment variables, never committed.

## Status against the $0 requirement
- Not marked complete. No configuration was deployed or verified. Verifying would need accounts on Render and Neon, which only the owner can create (manual checklist). Neither account may be upgraded or given a card unless the owner decides so explicitly.
- Terraform under `deploy/aws/` is kept unchanged and unused.

## Sources
- Render: https://render.com/docs/free, https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026.md
- Neon: https://neon.com/pricing, https://neon.com/faqs/free-plan-limits-and-quotas
- Supabase (third-party): https://www.jetadmin.io/blog/supabase-pricing-2026-guide-to-plans-limits-and-real-world-costs/
- Koyeb (third-party): https://agentdeals.dev/vendor/koyeb, https://freetier.co/directory/products/koyeb
- Oracle (official + third-party): https://docs.cloud.oracle.com/Content/FreeTier/freetier.htm, https://braindetox.kr/en/posts/oracle_always_free_backend_2026.html
- Google Cloud Run: https://cloud.google.com/run/pricing
