import shutil
import threading
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.auth import Principal, expensive, require_operator
from app.logger import logger
from ingest.db_connection import fetch_all, get_connection
from ml import bundle
from services import privacy

router = APIRouter(
    prefix="/admin", tags=["Admin"], dependencies=[Depends(require_operator), Depends(expensive)]
)

_LIVE_DIR = Path("models")
_STAGING_DIR = Path("models/staging")

_retrain_lock = threading.Lock()
_retrain_status: dict = {"state": "idle", "last_ran": None, "error": None, "metrics": {}}


def _run_retrain():
    """Train a candidate bundle. Never touches the active model: approval and activation are separate operator steps."""
    global _retrain_status
    _STAGING_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: recompute features (full-table batch); saves scaler.pkl, which travels with the bundle
        from features.compute import load_features, run_feature_sql, scale_features

        run_feature_sql()
        scale_features(load_features())

        # Step 2: train into the staging directory
        import ml.train as trainer

        _, X, y_score, y_cat = trainer.load_data()
        reg = trainer.train_regressor(X, y_score)
        clf = trainer.train_classifier(X, y_cat)
        importances = trainer.export_importances(reg, clf, trainer.FEATURE_COLS)
        shutil.copy(_LIVE_DIR / "scaler.pkl", _STAGING_DIR / "scaler.pkl")

        # Step 3: freeze + smoke-test + register as a candidate (rejected if the smoke test fails)
        from ml.bundle import create_candidate

        reg_imp = importances.get("regressor", {})
        version = create_candidate(
            _STAGING_DIR, {"label_origin": "synthetic_formula", "students": len(X)}
        )
        _retrain_status = {
            "state": "completed",
            "last_ran": datetime.now(UTC).isoformat(),
            "error": None,
            "metrics": {
                "candidate_version": version,
                "top_feature": max(reg_imp, key=reg_imp.get) if reg_imp else None,
                "top_importance": round(max(reg_imp.values()), 3) if reg_imp else None,
                "students_trained": len(X),
            },
        }

    except Exception as e:
        logger.error(
            f"retrain failed: {type(e).__name__}: {e}"
        )  # raw message stays in the log, not the API
        _retrain_status = {
            "state": "failed",
            "last_ran": datetime.now(UTC).isoformat(),
            "error": type(e).__name__,
            "metrics": {},
        }
        # The active model is untouched

    finally:
        # Always release the lock
        try:
            _retrain_lock.release()
        except RuntimeError:
            pass


@router.post("/retrain", status_code=202)
def trigger_retrain(p: Principal = Depends(require_operator)):
    """Trigger a background model retrain.

    - Non-blocking: returns 202 immediately
    - Safe: registers a candidate bundle only; approve + activate via /admin/models/*
    - Idempotent: returns 409 if a retrain is already running
    """
    if not _retrain_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Retrain already in progress")

    _audit(p, "model.retrain_started")
    _retrain_status["state"] = "running"
    t = threading.Thread(target=_run_retrain, daemon=True)
    t.start()

    return {
        "status": "accepted",
        "message": "Retrain started in background. Poll GET /admin/retrain/status.",
    }


@router.get("/retrain/status")
def retrain_status():
    """Poll retrain progress. States: idle | running | completed | failed."""
    return _retrain_status


def _audit(p: Principal, action: str, target: str | None = None):
    with get_connection() as conn, conn.cursor() as cur:
        privacy.audit(cur, action, p.user_id, p.subject, target)


def _guard(fn, *args):
    try:
        return fn(*args)
    except bundle.BundleError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None


@router.get("/models")
def list_models():
    return bundle.list_versions()


@router.post("/models/{version}/approve")
def approve_model(version: str, note: str = "", p: Principal = Depends(require_operator)):
    _guard(bundle.approve, version, p.subject, note)
    _audit(p, "model.approved", version)
    return {"version": version, "status": "approved"}


@router.post("/models/{version}/activate")
def activate_model(version: str, p: Principal = Depends(require_operator)):
    _guard(bundle.activate, version, p.subject)
    _audit(p, "model.activated", version)
    return {"version": version, "status": "active"}


@router.post("/models/rollback")
def rollback_model(p: Principal = Depends(require_operator)):
    version = _guard(bundle.rollback, p.subject)
    _audit(p, "model.rolled_back", version)
    return {"version": version, "status": "active"}


@router.get("/audit-events")
def audit_events(limit: int = 100):
    """Newest first: action, actor ids and target only. Never personal data or secrets."""
    return fetch_all(
        "SELECT id::text AS id, action, actor_user_id::text AS actor_user_id, actor_subject, target, created_at "
        "FROM audit_events ORDER BY created_at DESC LIMIT %s",
        (max(1, min(limit, 500)),),
    )


@router.get("/sync-failures")
def sync_failures(limit: int = 50):
    """Failed/partial sync runs with sanitized diagnostics: provider, status, safe error code, counts. No user,
    username or profile fields are selected, so operators cannot browse personal data through this."""
    return fetch_all(
        "SELECT r.id::text AS id, c.provider, r.status, r.safe_error_code, r.records_rejected, r.started_at, "
        "r.completed_at FROM sync_runs r JOIN integration_connections c ON c.id = r.connection_id "
        "WHERE r.status IN ('failed','partial') ORDER BY r.started_at DESC LIMIT %s",
        (max(1, min(limit, 200)),),
    )
