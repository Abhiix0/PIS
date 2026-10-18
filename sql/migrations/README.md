# Migrations

Applied in filename order by `python -m ingest.migrate`; each applied file is recorded in `schema_migrations`. Never edit an applied file.

## Naming

`NNN_snake_case.sql` with a 3-digit prefix. **New migrations must use a unique prefix** (next free number); `tests/test_migration_names.py` enforces this.

## Known duplicate prefix

`001_add_github_unique.sql` and `001_add_usernames.sql` share a prefix for historical reasons. They are already applied, so they are not renamed. Their order is fixed by the full filename (`github_unique` sorts before `usernames`), and the runner sorts by name, so the order is deterministic. This pair is the only allowed exception.
