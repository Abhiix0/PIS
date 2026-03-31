import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from config import DATABASE_URL

# Shared pool for all psycopg2 callers (ingest, features, ml, insights).
# minconn=1 keeps one connection warm; maxconn=5 caps psycopg2 usage well
# below Postgres's default max_connections=100 and leaves headroom for the
# SQLAlchemy pool (pool_size=5) used by the FastAPI layer.
_pool = pool.ThreadedConnectionPool(minconn=1, maxconn=5, dsn=DATABASE_URL)


@contextmanager
def get_connection():
    """Borrow a connection from the pool, commit on success, rollback on error.

    Usage:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(...)
    """
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
