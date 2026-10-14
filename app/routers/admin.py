import hmac
import json
import shutil
import threading
from pathlib  import Path
from datetime import datetime

from fastapi import APIRouter, HTTPException, Header

import config

router = APIRouter(prefix="/admin", tags=["Admin"])

_LIVE_DIR    = Path("models")
_STAGING_DIR = Path("models/staging")

_retrain_lock   = threading.Lock()
_retrain_status: dict = {"state": "idle", "last_ran": None, "error": None, "metrics": {}}


def _run_retrain():
    global _retrain_status
    _STAGING_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: recompute features (full-table batch)
        from features.compute import run_feature_sql, load_features, scale_features
        run_feature_sql()
        raw    = load_features()
        scale_features(raw)  # saves scaler.pkl to models/ directly (needed for training)

        # Step 2: train into staging directory
        import ml.train as trainer
        original_dir   = trainer.MODELS_DIR
        trainer.MODELS_DIR = _STAGING_DIR

        _, X, y_score, y_cat = trainer.load_data()
        reg = trainer.train_regressor(X, y_score)
        clf = trainer.train_classifier(X, y_cat)
        importances = trainer.export_importances(reg, clf, trainer.FEATURE_COLS)

        trainer.MODELS_DIR = original_dir  # restore

        # Step 3: copy scaler into staging for validation
        live_scaler = _LIVE_DIR / "scaler.pkl"
        if live_scaler.exists():
            shutil.copy(live_scaler, _STAGING_DIR / "scaler.pkl")

        # Step 4: smoke-test staging models against all students
        import joblib, pandas as pd
        test_reg     = joblib.load(_STAGING_DIR / "regressor.pkl")
        test_clf     = joblib.load(_STAGING_DIR / "classifier.pkl")
        test_scaler  = joblib.load(_STAGING_DIR / "scaler.pkl")

        from features.compute import load_features as lf
        df_check = lf()
        FEATURE_COLS = trainer.FEATURE_COLS
        X_check = df_check[FEATURE_COLS]
        X_scaled = test_scaler.transform(X_check)
        import numpy as np
        X_scaled = np.clip(X_scaled, 0.0, 1.0)
        test_reg.predict(X_scaled)   # raises if broken
        test_clf.predict(X_scaled)

        # Step 5: atomic swap — move staging files into live directory
        for f in _STAGING_DIR.iterdir():
            if f.is_file():
                f.rename(_LIVE_DIR / f.name)

        # Capture metrics for status endpoint
        reg_imp = importances.get('regressor', {})
        _retrain_status = {
            "state":    "completed",
            "last_ran": datetime.utcnow().isoformat(),
            "error":    None,
            "metrics":  {
                "top_feature":       max(reg_imp, key=reg_imp.get) if reg_imp else None,
                "top_importance":    round(max(reg_imp.values()), 3) if reg_imp else None,
                "students_validated": len(df_check),
            },
        }

    except Exception as e:
        _retrain_status = {
            "state":    "failed",
            "last_ran": datetime.utcnow().isoformat(),
            "error":    str(e),
            "metrics":  {},
        }
        # Staging is left intact for debugging; live models are untouched

    finally:
        # Always release the lock
        try:
            _retrain_lock.release()
        except RuntimeError:
            pass


def _require_admin(provided: str) -> None:
    """403 on a wrong key; 503 (endpoint disabled) when no usable ADMIN_KEY is configured."""
    if len(config.ADMIN_KEY) < config.MIN_ADMIN_KEY_LEN:
        raise HTTPException(status_code=503, detail="Admin endpoints disabled: ADMIN_KEY not configured")
    if not hmac.compare_digest(provided.encode(), config.ADMIN_KEY.encode()):
        raise HTTPException(status_code=403, detail="Invalid admin key")


@router.post("/retrain", status_code=202)
def trigger_retrain(x_admin_key: str = Header(...)):
    """Trigger a background model retrain.

    - Non-blocking: returns 202 immediately
    - Safe: writes to models/staging/, validates, then atomically swaps
    - Idempotent: returns 409 if a retrain is already running
    """
    _require_admin(x_admin_key)

    if not _retrain_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Retrain already in progress")

    _retrain_status["state"] = "running"
    t = threading.Thread(target=_run_retrain, daemon=True)
    t.start()

    return {"status": "accepted", "message": "Retrain started in background. Poll GET /admin/retrain/status."}


@router.get("/retrain/status")
def retrain_status(x_admin_key: str = Header(...)):
    """Poll retrain progress. States: idle | running | completed | failed."""
    _require_admin(x_admin_key)
    return _retrain_status
