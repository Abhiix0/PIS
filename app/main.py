from fastapi  import FastAPI, Request
from fastapi.responses  import JSONResponse
from app.db   import check_db_connection
from app.routers import students, ingest, predictions, insights

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