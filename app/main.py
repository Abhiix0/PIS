import time as time_module
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi           import FastAPI, Request
from fastapi.responses import JSONResponse

import config
from ingest.db_connection import get_connection, close_pool
from ingest.migrate import pending
from app.logger import logger
from app.routers import students, ingest, predictions, insights, features, pipeline, admin

REQUIRED_MODEL_FILES = [
    Path("models/regressor.pkl"),
    Path("models/classifier.pkl"),
    Path("models/scaler.pkl"),
    Path("models/feature_importances.json"),
]


def check_db_connection() -> bool:
    """Health check — called on startup to fail fast if DB is unreachable."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"DB connection failed: {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    errors = config.validate()

    if config.DATABASE_URL:
        if not check_db_connection():
            errors.append(
                "DATABASE_URL is set but database is unreachable. "
                "Check PostgreSQL connection."
            )
        else:
            try:
                with get_connection() as conn:
                    todo = pending(conn)
                if todo:
                    errors.append(f"Unapplied migrations: {todo}. Run: python -m ingest.migrate")
            except Exception as e:
                errors.append(f"Could not check migrations: {type(e).__name__}")

    missing_models = [str(f) for f in REQUIRED_MODEL_FILES if not f.exists()]
    if missing_models:
        errors.append(
            f"Missing model files: {missing_models}. "
            f"Run: python -m ml.train && python -m ml.predict"
        )

    if errors:
        for error in errors:
            print(f"[STARTUP ERROR] {error}")
        raise RuntimeError(
            f"Startup failed with {len(errors)} error(s). "
            f"See logs above for details."
        )

    if len(config.ADMIN_KEY) < config.MIN_ADMIN_KEY_LEN:
        print("[STARTUP WARNING] ADMIN_KEY not set or too short. /admin endpoints are disabled.")

    print(f"PIS API started successfully")
    print(f"  Database: connected")
    print(f"  Models:   {len(REQUIRED_MODEL_FILES)} files verified")
    print(f"  Docs:     http://localhost:8000/docs")

    yield
    close_pool()


app = FastAPI(
    title="Placement Intelligence System",
    version="1.0.0",
    description="""
    A data-driven platform that evaluates student placement readiness
    using SQL feature engineering, ML prediction, and a hybrid
    rule + ML insight engine.
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Register all routers ──────────────────────────────────────────────
app.include_router(students.router)
app.include_router(ingest.router)
app.include_router(predictions.router)
app.include_router(insights.router)
app.include_router(features.router, prefix="/features", tags=["features"])
app.include_router(pipeline.router)
app.include_router(admin.router)


# ── Global exception handler — never leak raw tracebacks ─────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", None)
    logger.error(f"[{rid}] unhandled {type(exc).__name__}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": rid},
    )

# ── Health check endpoints ────────────────────────────────────────────
_startup_time = time_module.time()


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/detailed", tags=["System"])
def health_detailed():
    """Detailed health check showing system component status."""
    db_ok  = check_db_connection()
    models = {f.stem: f.exists() for f in REQUIRED_MODEL_FILES}

    features_freshness = None
    student_count      = 0

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(computed_at) FROM features")
                row = cur.fetchone()
                features_freshness = str(row[0]) if row and row[0] else None

            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM students")
                row = cur.fetchone()
                student_count = row[0] if row else 0
    except Exception:
        pass

    uptime_seconds = round(time_module.time() - _startup_time)

    return {
        "status":             "ok" if db_ok and all(models.values()) else "degraded",
        "version":            app.version,
        "uptime_seconds":     uptime_seconds,
        "database":           "connected" if db_ok else "disconnected",
        "models":             models,
        "features_freshness": features_freshness,
        "student_count":      student_count,
    }


# ── Request logging middleware ────────────────────────────────────────
import time

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start    = time.perf_counter()
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    duration = (time.perf_counter() - start) * 1000

    path_parts = request.url.path.split("/")
    student_id = next((p for p in path_parts if p.isdigit()), "—")

    logger.info(
        f"[{request_id}] {request.method:<6} {request.url.path:<35} "
        f"student={student_id:<4} status={response.status_code} "
        f"duration={duration:.1f}ms"
    )
    return response
