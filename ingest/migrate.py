"""The one supported schema path: apply sql/migrations/*.sql in filename order.

    python -m ingest.migrate           # apply pending migrations
    python -m ingest.migrate --seed    # also load demo data (refused in staging/production)

Each file runs in its own transaction and is recorded in schema_migrations, so reruns are no-ops
and any failure aborts with a non-zero exit instead of leaving a half-initialised database.
"""
import sys
from pathlib import Path

import psycopg2

import config

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "sql" / "migrations"
SEED_FILE = MIGRATIONS_DIR.parent / "seed.sql"
_LOCK_ID = 727001  # arbitrary app-wide advisory-lock key; serialises concurrent runners


def migration_files(directory: Path = MIGRATIONS_DIR) -> list[Path]:
    return sorted(directory.glob("*.sql"), key=lambda p: p.name)


def pending(conn, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Names of migration files not yet recorded (all of them if the tracking table is absent)."""
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.schema_migrations')")
        applied = set()
        if cur.fetchone()[0]:
            cur.execute("SELECT version FROM schema_migrations")
            applied = {r[0] for r in cur.fetchall()}
    conn.rollback()
    return [p.name for p in migration_files(directory) if p.name not in applied]


def migrate(dsn: str, directory: Path = MIGRATIONS_DIR, seed: bool = False) -> list[str]:
    """Apply pending migrations; return the names applied. Raises on any SQL error."""
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (_LOCK_ID,))
            cur.execute("CREATE TABLE IF NOT EXISTS schema_migrations ("
                        "version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
        conn.commit()
        applied = []
        for name in pending(conn, directory):
            with conn.cursor() as cur:  # psycopg2 opens a transaction implicitly; commit is per file
                cur.execute((directory / name).read_text(encoding="utf-8"))
                cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (name,))
            conn.commit()
            applied.append(name)
        if seed:
            if not config.seed_allowed():
                raise RuntimeError(f"Refusing to load demo seed data when APP_ENV={config.APP_ENV}.")
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM students")
                if cur.fetchone()[0] == 0:  # never touch a database that already has students
                    cur.execute(SEED_FILE.read_text(encoding="utf-8"))
            conn.commit()
        return applied
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    errors = config.validate()
    if errors:
        sys.exit("[CONFIG ERROR] " + "\n[CONFIG ERROR] ".join(errors))
    done = migrate(config.DATABASE_URL, seed="--seed" in sys.argv)
    print(f"Applied {len(done)} migration(s): {done}" if done else "Schema up to date.")
