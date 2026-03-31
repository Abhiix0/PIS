import os
import time as time_module
from pathlib import Path

from fastapi           import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy        import text
from sqlalchemy.orm    import Session

from app.db     import check_db_connection, get_db
from app.logger import logger
from app.routers import students, ingest, predictions, insights, features, pipeline

REQUIRED_MODEL_FILES = [
    Path("models/regressor.pkl"),
    Path("models/classifier.pkl"),
    Path("models/scaler.pkl"),
    Path("models/feature_importances.json"),
]

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
)

# ── Register all routers ──────────────────────────────────────────────
app.include_router(students.router)
app.include_router(ingest.router)
app.include_router(predictions.router)
app.include_router(insights.router)
app.include_router(features.router, prefix="/features", tags=["features"])
app.include_router(pipeline.router)

# ── Startup validation ────────────────────────────────────────────────
@app.on_event("startup")
async def startup_checks():
    errors = []

    if not os.getenv("DATABASE_URL"):
        errors.append("DATABASE_URL environment variable is not set.")

    if not check_db_connection():
        errors.append(
            "DATABASE_URL is set but database is unreachable. "
            "Check PostgreSQL connection."
        )

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

    print(f"PIS API v{app.version} started successfully")
    print(f"  Database: connected")
    print(f"  Models:   {len(REQUIRED_MODEL_FILES)} files verified")
    print(f"  Docs:     http://localhost:8000/docs")

# ── Global exception handler — never leak raw tracebacks ─────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}"},
    )

# ── Health check endpoints ────────────────────────────────────────────
_startup_time = time_module.time()


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/detailed", tags=["System"])
def health_detailed(db: Session = Depends(get_db)):
    """Detailed health check showing system component status."""
    db_ok  = check_db_connection()
    models = {f.stem: f.exists() for f in REQUIRED_MODEL_FILES}

    try:
        row = db.execute(
            text("SELECT MAX(computed_at) AS last_computed FROM features")
        ).fetchone()
        features_freshness = str(row._mapping["last_computed"]) if row else None
    except Exception:
        features_freshness = None

    try:
        count_row     = db.execute(text("SELECT COUNT(*) AS n FROM students")).fetchone()
        student_count = count_row._mapping["n"]
    except Exception:
        student_count = 0

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
    response = await call_next(request)
    duration = (time.perf_counter() - start) * 1000

    path_parts = request.url.path.split("/")
    student_id = next((p for p in path_parts if p.isdigit()), "—")

    logger.info(
        f"{request.method:<6} {request.url.path:<35} "
        f"student={student_id:<4} status={response.status_code} "
        f"duration={duration:.1f}ms"
    )
    return response
