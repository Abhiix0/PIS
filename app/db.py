from sqlalchemy       import create_engine, text
from sqlalchemy.orm    import sessionmaker, Session
from typing            import Generator
from config            import DATABASE_URL

# Synchronous engine — simpler than async for this project scope.
# pool_pre_ping ensures stale connections are recycled automatically.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields one DB session per request.
    Session is always closed in the finally block, even on exceptions.
    Usage: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_db_connection() -> bool:
    """Health check — called on startup to fail fast if DB is unreachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"DB connection failed: {e}")
        return False