# Contributing

## Branching and commits

- Branch from `main` (`feature/<topic>`, `fix/<topic>`, `docs/<topic>`). Work lands through a pull request; do not commit to `main`.
- Small commits with a prefix as in `git log` (`polish:`, `docs:`, `fix:`, `feat:`). Never commit `.env`, tokens or keys.

## Before you push

```bash
make check      # ruff + format check + mypy, then pytest with the coverage floor (.coveragerc)
make check-ui   # only if you touched apps/desktop
```

`make check` needs a live PostgreSQL and `TEST_ADMIN_DATABASE_URL` (a role that can CREATE DATABASE). Without a DB, run the DB-free subset listed in the README and say so in the PR. Report only checks you ran. Do not weaken or delete a test to make it pass.

## Rules

- **Migrations**: schema changes are a new numbered file in `sql/migrations/` with the next free prefix (see `sql/migrations/README.md`). Never edit an applied file. Check a new migration on a clean database. There is no other schema path.
- **Routes**: a new route needs a row in `docs/architecture/api-surface.md` and a test (an auth test for `/api/v1`).
- **Synthetic data**: the only synthetic data is `sql/seed.sql` (local/test). A failed provider call must never fall back to synthetic data. Never present synthetic-derived results as a user's real activity. Record `provenance` for every datum; never invent timestamps from aggregates.
- **ML changes**: the score is a readiness *proxy*, never a hiring/placement prediction. Any model, feature or label change needs a documented baseline, experiment and evaluation (`docs/ml/experiment-protocol.md`), a candidate bundle that passes the smoke test, operator approval, and a rollback path (`docs/ml/model-lifecycle.md`). Adding a feature touches the SQL, `features/compute.py`, `ml/labels.py`, `ml/train.py`, `ml/predict.py` and `docs/data/data-dictionary.md`.
- **Dependencies**: no LLM, vector DB, queue, Redis or new model family without a written requirement.
- **Docs**: describe what the code does. Mark anything you did not verify as unverified. New docs go in the topical folder listed in `docs/README.md`, not in stage- or date-named folders.
