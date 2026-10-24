# NexGauge

NexGauge, a **Personal Career Intelligence System**, gives a student a **preparation assessment**: per-area evidence states (with source, time, rule and caveats) and traceable suggestions, built from public GitHub activity (LeetCode is disabled by default). CGPA is optional self-reported context. There is **no score** for real accounts and **no prediction of hiring or placement**: no outcome labels exist (see [limitations](#limitations)).

## For end users (no Python, Node or Docker)
1. Download `NexGauge_<version>_x64-setup.exe` and `SHA256SUMS.txt` from the release page and follow [docs/ops/release/install-guide.md](docs/ops/release/install-guide.md) (the installer is unsigned, so Windows SmartScreen will warn).
2. Sign in, create your profile, connect your **public** GitHub username, run a sync, then run your first assessment.
3. What it measures and cannot establish, data handling and deletion are in the install guide. Nothing is published yet: no release exists.

Stack: PostgreSQL 15 (SQL feature engineering) -> FastAPI (`app/`) -> desktop client (`apps/desktop/`, Tauri + React). Python, scikit-learn RandomForest, `psycopg2`.

## Quickstart (Docker)

```bash
cp .env.example .env     # set DATABASE_URL and POSTGRES_PASSWORD
make up                  # builds, migrates, seeds demo data, trains, starts API on :8000
make health              # GET /health/detailed
make down                # stop; `make down-clean` also wipes the DB volume
```

Interactive docs: http://localhost:8000/docs. Every route except `/health*` needs an IdP bearer token (set `AUTH_ISSUER`, `AUTH_AUDIENCE`, `AUTH_JWKS_URL`); without them the API starts but answers 401. Seed data is synthetic and only for local/test.

*Unverified:* these Docker commands were not run when this README was written (Docker daemon not running).

## Quickstart (local, no Docker)

Needs Python 3.11+ and a reachable, empty PostgreSQL 15 database.

Environment variables (copy `.env.example` to `.env` and fill them in; run commands from the repo root):

- `DATABASE_URL`: the database the app uses.
- `APP_ENV=local`.
- `SEED_DEMO_DATA=true`: loads the synthetic demo seed (local/test only).
- `TEST_ADMIN_DATABASE_URL`: only for the test suite. Needs a role that can `CREATE DATABASE`; tests build a throwaway database.

```bash
python -m venv venv
venv/Scripts/python.exe -m pip install -r requirements-dev.txt   # Windows venv path; use venv/bin/python on Linux/macOS
# use that interpreter for the commands below (activate the venv, or call it by path)
python -m ingest.migrate --seed                       # schema + demo seed (never in staging/production)
python -m features.compute                            # creates models/ if missing
python -m ml.train
python -m ml.bundle bootstrap                         # local-only activation
python -m ml.predict
uvicorn app.main:app --reload
```

This is the `entrypoint.sh` boot order. *Unverified:* the chain has not yet been run end to end from a clean checkout.

## Tests and checks

| Command | Needs | Last run |
|---|---|---|
| `pytest tests/test_core.py tests/test_github_api.py tests/test_leetcode_api.py tests/test_config.py tests/test_route_coverage.py` | nothing (no DB) | ran: 79 passed |
| `ruff check . && ruff format --check . && mypy` (`make lint`) | dev requirements | ran: ruff clean, mypy no issues |
| `make test-local` | live DB, `TEST_ADMIN_DATABASE_URL` | not run |
| `make test` | running Docker stack | not run |
| `make check` (lint + tests + coverage floor, same as CI) | DB, `TEST_ADMIN_DATABASE_URL` | not run |
| `make check-ui` (desktop typecheck, lint, format, vitest) | `npm ci` in `apps/desktop` | not run |

On Windows use `venv/Scripts/python.exe -m pytest ...` if the system Python lacks dependencies.

## Repository map

| Path | Role |
|---|---|
| `app/` | FastAPI app, `/api/v1` and operator routers, JWT auth |
| `services/` | sync lifecycle, privacy (export, deletion, audit) |
| `ingest/` | GitHub/LeetCode adapters, validators, DB pool, migration runner |
| `features/`, `ml/` | feature SQL runner, labels, training, model bundles, experiment runner |
| `sql/` | `migrations/` (only schema path), `seed.sql` (demo), `feature_engineering.sql` |
| `apps/desktop/` | desktop client (HTTP client of `/api/v1`) |
| `deploy/aws/` | Terraform and release script (never applied; see runbook) |
| `tests/` | pytest suite |
| `docs/` | all documentation, indexed in [docs/README.md](docs/README.md) |

## Documentation

Start at [docs/README.md](docs/README.md). Most useful:

- [Current state](docs/architecture/current-state.md): what exists today, verified vs. unverified
- [API surface](docs/architecture/api-surface.md)
- [Data dictionary](docs/data/data-dictionary.md) and [provenance](docs/data/provenance.md)
- [Model lifecycle](docs/ml/model-lifecycle.md)
- [Auth architecture](docs/security/auth-architecture.md)
- [Contributing](CONTRIBUTING.md)

## Limitations

- Output is a readiness *proxy score*. Training labels are a weighted formula of the same features plus fixed-seed noise; the model is trained on about 8 synthetic seed students and learns that formula, not placement outcomes.
- Real users currently get evidence snapshots (`insufficient_evidence`), no score: provider data cannot supply the model's inputs without inventing values.
- GitHub timestamps are the repo's last push date, not commit dates. LeetCode is aggregate-only and disabled unless `LEETCODE_INTEGRATION_ENABLED=true`; its API is unofficial.
- Rate limits are per process. The AWS deployment, signed installers and the full Docker boot path are unverified.

License: MIT ([LICENSE](LICENSE)).
