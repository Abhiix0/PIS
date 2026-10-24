from contextlib import contextmanager

import pandas as pd
from psycopg2 import InterfaceError, OperationalError, pool

from config import DATABASE_URL

# Lazy-initialized pool — created on first use, not at import time.
# Prevents crash when DATABASE_URL is not yet loaded (e.g. test collection).
_pool: pool.ThreadedConnectionPool | None = None


def _get_pool() -> pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not set. Check your .env file or environment variables."
            )
        # maxconn=20 handles concurrent batch pipeline requests safely.
        # SQLAlchemy pool uses up to 15 (pool_size=5 + max_overflow=10),
        # leaving 65+ connections free under Postgres default max_connections=100.
        _pool = pool.ThreadedConnectionPool(
            minconn=2, maxconn=20, dsn=DATABASE_URL, options="-c timezone=UTC"
        )  # API timestamps are UTC
    return _pool


def close_pool() -> None:
    """Close all pooled connections (API shutdown)."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


def _checkout():
    """A live pooled connection. Hosts that suspend an idle database (e.g. free tiers) drop pooled connections;
    a dead one is discarded and replaced instead of failing the request."""
    p = _get_pool()
    for _ in range(3):
        conn = p.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            conn.rollback()
            return conn
        except (OperationalError, InterfaceError):
            p.putconn(conn, close=True)
    return p.getconn()


@contextmanager
def get_connection():
    """Borrow a connection from the pool, commit on success, rollback on error."""
    conn = _checkout()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _get_pool().putconn(conn)


def query_df(conn, sql: str, params=None) -> pd.DataFrame:
    """Run a query on a psycopg2 connection and return a DataFrame (pd.read_sql warns on raw conns)."""
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])


def fetch_all(sql: str, params=None) -> list[dict]:
    """One read-only query -> list of column-keyed dicts (replaces the connect/cursor/zip boilerplate in routers)."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
