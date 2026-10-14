import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from config import DATABASE_URL

# Lazy-initialized pool — created on first use, not at import time.
# Prevents crash when DATABASE_URL is not yet loaded (e.g. test collection).
_pool: pool.ThreadedConnectionPool | None = None


def _get_pool() -> pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not set. "
                "Check your .env file or environment variables."
            )
        # maxconn=20 handles concurrent batch pipeline requests safely.
        # SQLAlchemy pool uses up to 15 (pool_size=5 + max_overflow=10),
        # leaving 65+ connections free under Postgres default max_connections=100.
        _pool = pool.ThreadedConnectionPool(minconn=2, maxconn=20, dsn=DATABASE_URL)
    return _pool


def close_pool() -> None:
    """Close all pooled connections (API shutdown)."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


@contextmanager
def get_connection():
    """Borrow a connection from the pool, commit on success, rollback on error."""
    conn = _get_pool().getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _get_pool().putconn(conn)


def clear_coding_activity(student_id: int) -> int:
    """Delete all coding_activity rows for a student and return the count removed.
    Call this before inserting real LeetCode data so legacy inflated records
    don't persist alongside the fresh correct set.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM coding_activity WHERE student_id = %s",
                (student_id,)
            )
            deleted = cur.rowcount
    print(f"[DEBUG] Cleared {deleted} old coding_activity rows for student {student_id}")
    return deleted
