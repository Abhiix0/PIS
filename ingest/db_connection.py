import psycopg2
from contextlib import contextmanager
from config import DATABASE_URL

# contextmanager gives us automatic commit/rollback
# with get_connection() as conn: — if anything throws, it rolls back
@contextmanager
def get_connection():
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        yield conn
        conn.commit()          # only commits if no exception raised
    except Exception as e:
        if conn:
            conn.rollback()   # full rollback on any failure
        raise e
    finally:
        if conn:
            conn.close()