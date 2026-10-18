"""Migration tests.

Static checks always run. DB checks run against a throwaway database that is created and dropped
here; they need a role allowed to CREATE DATABASE:
    TEST_ADMIN_DATABASE_URL=postgresql://<superuser>:<pw>@localhost:5432/postgres pytest tests/test_migrate.py
"""

import os
import re
import uuid

import psycopg2
import pytest
from psycopg2 import sql
from psycopg2.extensions import make_dsn

import config
from ingest.migrate import MIGRATIONS_DIR, migrate, migration_files, pending

ADMIN_URL = os.getenv("TEST_ADMIN_DATABASE_URL")
needs_db = pytest.mark.skipif(not ADMIN_URL, reason="TEST_ADMIN_DATABASE_URL not set")
ROOT = MIGRATIONS_DIR.parent


# ── static ────────────────────────────────────────────────────────────


def test_migrations_are_ordered_and_unique():
    names = [p.name for p in migration_files()]
    assert names[0] == "000_baseline.sql"
    assert names == sorted(names) and len(names) == len(set(names))


def test_no_index_predicate_uses_moving_date():
    # PostgreSQL rejects non-IMMUTABLE functions in index predicates (this broke fresh installs).
    for p in migration_files():
        for stmt in re.findall(r"CREATE\s+(?:UNIQUE\s+)?INDEX.*?;", p.read_text(), re.S | re.I):
            assert not re.search(r"\bWHERE\b.*(CURRENT_DATE|NOW\(\))", stmt, re.S | re.I), p.name


def test_no_parallel_schema_file():
    assert not (ROOT / "schema.sql").exists()


# ── database ──────────────────────────────────────────────────────────


@pytest.fixture
def fresh_db():
    name = f"pis_test_{uuid.uuid4().hex[:10]}"
    admin = psycopg2.connect(ADMIN_URL)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_dsn(ADMIN_URL, dbname=name)
    try:
        yield dsn
    finally:
        with admin.cursor() as cur:
            cur.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )
        admin.close()


def _q(dsn, query, args=None):
    with psycopg2.connect(dsn) as c, c.cursor() as cur:
        cur.execute(query, args)
        return cur.fetchall() if cur.description else None


@needs_db
def test_empty_database_migrates_and_rerun_is_noop(fresh_db):
    applied = migrate(fresh_db)
    assert applied == [p.name for p in migration_files()]
    assert migrate(fresh_db) == []
    conn = psycopg2.connect(fresh_db)
    assert pending(conn) == []
    conn.close()
    tables = {
        r[0] for r in _q(fresh_db, "SELECT tablename FROM pg_tables WHERE schemaname='public'")
    }
    assert {
        "students",
        "coding_activity",
        "github_activity",
        "features",
        "predictions",
        "prediction_history",
        "schema_migrations",
    } <= tables
    assert _q(fresh_db, "SELECT 1 FROM pg_constraint WHERE conname='uq_github_activity'")


@needs_db
def test_failing_migration_aborts_and_is_not_recorded(fresh_db, tmp_path):
    (tmp_path / "000_ok.sql").write_text("CREATE TABLE a (x int);")
    (tmp_path / "001_bad.sql").write_text("CREATE TABLE b (x int); SELECT nope FROM missing;")
    with pytest.raises(psycopg2.Error):
        migrate(fresh_db, tmp_path)
    assert [r[0] for r in _q(fresh_db, "SELECT version FROM schema_migrations")] == ["000_ok.sql"]
    assert _q(fresh_db, "SELECT to_regclass('public.b')")[0][0] is None  # rolled back with its file


@needs_db
def test_github_ingest_is_idempotent(fresh_db):
    migrate(fresh_db)
    _q(fresh_db, "INSERT INTO students (name,email,branch) VALUES ('t','t@x.dev','CSE')")
    ins = (
        "INSERT INTO github_activity (student_id,repo_name,commits,commit_date) "
        "VALUES (1,'r',5,'2024-01-01') ON CONFLICT (student_id, repo_name, commit_date) DO NOTHING"
    )
    _q(fresh_db, ins)
    _q(fresh_db, ins)
    assert _q(fresh_db, "SELECT COUNT(*) FROM github_activity")[0][0] == 1


@needs_db
def test_upgrade_dedupes_before_adding_unique(fresh_db, tmp_path):
    # Simulate a pre-migration database: baseline only, with duplicate GitHub rows.
    only_baseline = tmp_path / "m"
    only_baseline.mkdir()
    (only_baseline / "000_baseline.sql").write_text(
        (MIGRATIONS_DIR / "000_baseline.sql").read_text()
    )
    migrate(fresh_db, only_baseline)
    _q(fresh_db, "INSERT INTO students (name,email,branch) VALUES ('t','t@x.dev','CSE')")
    for _ in range(2):
        _q(
            fresh_db,
            "INSERT INTO github_activity (student_id,repo_name,commits,commit_date) "
            "VALUES (1,'r',5,'2024-01-01')",
        )
    migrate(fresh_db)  # upgrade with all migrations
    assert _q(fresh_db, "SELECT COUNT(*) FROM github_activity")[0][0] == 1


@needs_db
def test_seed_loads_once_and_is_refused_when_deployed(fresh_db, monkeypatch):
    monkeypatch.setattr(config, "APP_ENV", "local")
    migrate(fresh_db, seed=True)
    n = _q(fresh_db, "SELECT COUNT(*) FROM students")[0][0]
    assert n == 8
    migrate(fresh_db, seed=True)  # second run must not duplicate or fail
    assert _q(fresh_db, "SELECT COUNT(*) FROM students")[0][0] == n
    monkeypatch.setattr(config, "APP_ENV", "production")
    with pytest.raises(RuntimeError):
        migrate(fresh_db, seed=True)
