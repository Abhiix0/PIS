# Verified Development Commands

> **Historical:** written before the current code; see [current-state](../architecture/current-state.md) for what exists today.

Status legend: **ran-ok** (executed, behaved), **ran-fail** (executed, failed; see defect), **not run**. Shell: Git Bash on Windows 11, Docker Compose v5.1, Docker 29.3.

## Works today

```bash
# Unit tests that need no DB or models (ran-ok: 23 passed). The repo venv is Python 3.14, not the supported 3.11.
venv/Scripts/python.exe -m pytest tests/test_core.py tests/test_insights.py tests/test_github_api.py tests/test_leetcode_api.py -q

# Syntax check (ran-ok)
venv/Scripts/python.exe -m compileall -q app services ingest features ml insights dashboard tests config.py
```

## Disposable full stack (ran-ok after the D-01 workaround)

The repo's `docker-compose.yml` publishes `5432`, mounts `./models` and `./features` (boot overwrites them) and builds with the whole repo (incl. `venv/`, `.env`) as context. To avoid touching the tracked files, ports or other volumes, run a **copy** of the compose file under a separate project name:

1. Copy `docker-compose.yml` to a scratch directory; change host ports (e.g. `15432:5432`, `18000:8000`, `18501:8501`); use absolute paths for `build.context` and the `sql/` mounts; point the `models` and `features` mounts at **copies** of those directories.
2. Until D-01 is fixed, mount a copy of `sql/schema.sql` with the `idx_coding_recent` statement removed (the unmodified schema aborts the DB container with exit code 3).
3. Run:

```bash
docker compose -p pis_p1 -f <scratch>/compose.yml build            # >10 min today (no .dockerignore)
docker compose -p pis_p1 -f <scratch>/compose.yml up -d            # db healthy ~25 s, api ready ~40 s after
curl -s localhost:18000/health/detailed                           # ran-ok
docker exec pis_p1-api-1 pytest tests/ -v --tb=short             # ran: 41 passed, 1 failed (D-07)
curl -s -X POST "localhost:18000/pipeline/1?force_refresh=true"  # ran-ok; github_ingestion step errors until D-02 is fixed
curl -s -X POST localhost:18000/pipeline/batch -H "Content-Type: application/json" -d '{"student_ids":[2,3]}'   # ran-ok
curl -s localhost:18501/_stcore/health                            # dashboard, ran-ok -> "ok"
docker compose -p pis_p1 -f <scratch>/compose.yml down -v         # removes only this project's containers and volume
```

Boot order inside the API container (`entrypoint.sh`, ran-ok): `python -m features.compute` → `python -m ml.train` → `python -m ml.predict` → `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

## Repo `Makefile` targets

| Target | Status |
|---|---|
| `make up` / `up-detached` | **ran-fail on clean volume** (D-01), and host port 5432 must be free; not run as-is |
| `make test` (`docker-compose exec api pytest …`) | not run as-is; the equivalent `docker exec … pytest tests/` ran: 41 passed / 1 failed |
| `make test-local` | not run (needs a live DB at `DATABASE_URL` and `models/`) |
| `make pipeline-all` | not run as-is; `POST /pipeline/batch` equivalent ran |
| `make health` / `logs` / `seed` / `down` / `down-clean` / `clean` | not run |

`make down-clean` runs `docker-compose down -v` and wipes the project's DB volume; do not run it where the volume holds data you need.

## Known caveats when reproducing

- `POST /pipeline/{id}` returns **429** for 5 minutes after boot; use `?force_refresh=true`.
- After boot the tracked `models/*` and `features/*.csv` are rewritten if the repo dirs are mounted (D-09).
- Tests mutate the database they run against; re-create the volume for a pristine baseline.
- No lint command is configured.
