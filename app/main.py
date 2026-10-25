import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

import config
from app.logger import logger
from app.routers import admin, v1
from ingest.db_connection import close_pool, get_connection
from ingest.migrate import pending
from ml.bundle import active_version


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
                "DATABASE_URL is set but database is unreachable. Check PostgreSQL connection."
            )
        else:
            try:
                with get_connection() as conn:
                    todo = pending(conn)
                if todo:
                    errors.append(f"Unapplied migrations: {todo}. Run: python -m ingest.migrate")
            except Exception as e:
                errors.append(f"Could not check migrations: {type(e).__name__}")

    if errors:
        for error in errors:
            print(f"[STARTUP ERROR] {error}")
        raise RuntimeError(
            f"Startup failed with {len(errors)} error(s). See logs above for details."
        )

    if not (config.AUTH_ISSUER and config.AUTH_AUDIENCE and config.AUTH_JWKS_URL):
        print("[STARTUP WARNING] AUTH_* not configured. Every protected endpoint will return 401.")

    print("NexGauge API started successfully")
    print("  Database: connected")
    print("  Docs:     http://localhost:8000/docs")

    yield
    close_pool()


app = FastAPI(
    title="NexGauge API",
    version="1.0.0",
    description="""
    NexGauge, a Personal Career Intelligence System. Shows a placement-readiness
    proxy score from SQL feature engineering and ML. It is not a prediction of
    hiring or placement outcomes.
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Register all routers ──────────────────────────────────────────────
app.include_router(admin.router)
app.include_router(v1.router)
app.include_router(v1.session_router)


# ── Error envelope on every route: {"error": {code, message, request_id}} ──
_CODES = {
    500: "internal_error",
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_error",
    429: "rate_limited",
    501: "not_implemented",
    503: "unavailable",
}


def _envelope(request: Request, status: int, message, headers=None):
    rid = getattr(request.state, "request_id", None)
    body = {"error": {"code": _CODES.get(status, "error"), "message": message, "request_id": rid}}
    return JSONResponse(status_code=status, content=body, headers=headers)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return _envelope(request, exc.status_code, exc.detail, exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errs = [
        {"loc": [str(x) for x in e["loc"]], "msg": e["msg"]} for e in exc.errors()
    ]  # no echoed input values
    return _envelope(request, 422, errs)


# ── Global exception handler — never leak raw tracebacks ─────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", None)
    logger.error(f"[{rid}] unhandled {type(exc).__name__}: {exc}")
    return _envelope(request, 500, "Internal server error")


# ── Health check endpoints ────────────────────────────────────────────
_startup_time = time.time()


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/ready", tags=["System"])
def health_ready():
    """Readiness probe (load balancer): 503 unless the DB answers and migrations are applied; an active ML model is not required (real-user assessments are deterministic)."""
    problems = []
    try:
        with get_connection() as conn:
            if pending(conn):
                problems.append("migrations")
    except Exception:
        problems.append("database")
    if problems:
        return JSONResponse(status_code=503, content={"status": "unready", "problems": problems})
    return {"status": "ready"}


@app.get("/health/detailed", tags=["System"])
def health_detailed():
    """Detailed health check showing system component status."""
    db_ok = check_db_connection()
    try:
        model_version = active_version()
    except Exception:
        model_version = None
    if model_version is None:
        model_version = "none"

    features_freshness = None
    student_count = 0

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

    uptime_seconds = round(time.time() - _startup_time)

    return {
        "status": "ok" if db_ok else "degraded",
        "version": app.version,
        "uptime_seconds": uptime_seconds,
        "database": "connected" if db_ok else "disconnected",
        "model_version": model_version,
        "features_freshness": features_freshness,
        "student_count": student_count,
    }


# ── Request logging middleware ────────────────────────────────────────


@app.middleware("http")
async def limit_body(request: Request, call_next):
    # shortcut: trusts Content-Length; chunked uploads need a streaming cap (or a reverse-proxy limit) before public exposure.
    if int(request.headers.get("content-length") or 0) > config.MAX_BODY_BYTES:
        return _envelope(request, 413, "Request body too large")
    return await call_next(request)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
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
        f"duration={duration:.1f}ms",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(duration, 1),
        },
    )
    return response


# Added last so it is the outermost middleware: preflights are answered before auth and errors keep the envelope.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
