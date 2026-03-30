from fastapi  import FastAPI, Request
from fastapi.responses  import JSONResponse
from app.db   import check_db_connection
import time
from app.logger import logger
# ADDED 'features' to the import line below
from app.routers import students, ingest, predictions, insights, features 

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
# Now 'features' is defined and will not throw NameError
app.include_router(features.router, prefix="/features", tags=["features"])

# ── Startup event: fail fast if DB is unreachable ─────────────────────
@app.on_event("startup")
async def startup_checks():
    if not check_db_connection():
        raise RuntimeError("Cannot connect to database on startup. Check DATABASE_URL.")
    print("PIS API started — database connection OK")

# ── Global exception handler — never leak raw tracebacks ─────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}"},
    )

# ── Health check endpoint ─────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "version": "1.0.0"}

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start   = time.perf_counter()
    response = await call_next(request)
    duration = (time.perf_counter() - start) * 1000  # ms

    path_parts = request.url.path.split("/")
    student_id = next(
        (p for p in path_parts if p.isdigit()), "—"
    )

    logger.info(
        f"{request.method:<6} {request.url.path:<35} "
        f"student={student_id:<4} status={response.status_code} "
        f"duration={duration:.1f}ms"
    )
    return response