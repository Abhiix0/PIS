import json
import math
import threading
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from ingest.db_connection import get_connection, query_df
from ml.bundle import CATEGORIES, FEATURE_COLS, SCHEMA_VERSION, load_active

ML_TYPE, INSUFFICIENT_TYPE = "ml_readiness_proxy", "insufficient_evidence"
_slots = threading.BoundedSemaphore(
    4
)  # bounds concurrent inference; the models are loaded once per active version


def _fetch_raw_features(student_id: int) -> dict | None:
    query = """
        SELECT s.cgpa, f.total_problems, f.avg_difficulty,
               f.consistency_score, f.commit_frequency, f.computed_at
        FROM  students s
        JOIN  features  f ON s.id = f.student_id
        WHERE s.id = %(student_id)s
    """
    with get_connection() as conn:
        df = query_df(conn, query, {"student_id": student_id})
    return None if df.empty else df.iloc[0].to_dict()


def _insufficient_reason(raw: dict | None) -> str | None:
    if raw is None:
        return "No computed features for this student yet."
    bad = [c for c in FEATURE_COLS if raw[c] is None or not math.isfinite(float(raw[c]))]
    if bad:
        return f"Missing or non-finite inputs: {', '.join(bad)}."
    if not 0 <= float(raw["cgpa"]) <= 10:
        return "CGPA is outside the supported 0-10 range."
    return None


def predict(student_id: int) -> dict:
    """Assess one student with the active model bundle and record an immutable snapshot.

    Returns an `ml_readiness_proxy` result, or an `insufficient_evidence` result with no score when the
    inputs cannot support one. Raises if the active bundle is missing/incompatible or the output is invalid.
    """
    raw = _fetch_raw_features(student_id)
    reason = _insufficient_reason(raw)
    bundle = load_active()
    snapshot: dict[str, Any] = {
        "feature_schema_version": SCHEMA_VERSION,
        "model_version": bundle.version,
    }
    score = category = None
    if reason is None:
        assert raw is not None  # reason is None only when raw exists
        values = {c: float(raw[c]) for c in FEATURE_COLS}
        snapshot["features"] = values
        snapshot["features_computed_at"] = str(raw["computed_at"])
        x = pd.DataFrame([values], columns=FEATURE_COLS)
        scaled = bundle.scaler.transform(x)
        snapshot["clipped"] = [c for c, v in zip(FEATURE_COLS, scaled[0]) if not 0.0 <= v <= 1.0]
        x = pd.DataFrame(
            scaled.clip(0.0, 1.0), columns=FEATURE_COLS
        )  # guard against out-of-range real data
        if not _slots.acquire(timeout=5):
            raise RuntimeError("Inference capacity exhausted; retry shortly")
        try:
            score = float(bundle.regressor.predict(x)[0])
            category = str(bundle.classifier.predict(x)[0])
        finally:
            _slots.release()
        if not math.isfinite(score) or category not in CATEGORIES:
            raise ValueError(f"Model {bundle.version} produced an invalid output")
        score = round(max(0.0, min(100.0, score)), 2)  # float precision can give 100.0001

    result = {
        "student_id": student_id,
        "assessment_type": INSUFFICIENT_TYPE if reason else ML_TYPE,
        "readiness_score": score,
        "category": category,
        "reason": reason,
        "model_version": bundle.version,
        "input_snapshot": snapshot,
        "predicted_at": datetime.now(UTC).isoformat(),
    }
    _save_prediction(result)
    return result


def _save_prediction(r: dict):
    """Upsert the latest assessment and append an immutable history row."""
    p = {
        "sid": r["student_id"],
        "score": r["readiness_score"],
        "cat": r["category"],
        "type": r["assessment_type"],
        "ver": r["model_version"],
        "snap": json.dumps(r["input_snapshot"]),
        "reason": r["reason"],
    }
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO predictions
                    (student_id, readiness_score, category, last_updated, assessment_type, model_version, input_snapshot, reason)
                VALUES
                    (%(sid)s, %(score)s, %(cat)s, NOW(), %(type)s, %(ver)s, %(snap)s::jsonb, %(reason)s)
                ON CONFLICT (student_id) DO UPDATE SET
                    readiness_score = EXCLUDED.readiness_score,
                    category        = EXCLUDED.category,
                    last_updated    = NOW(),
                    assessment_type = EXCLUDED.assessment_type,
                    model_version   = EXCLUDED.model_version,
                    input_snapshot  = EXCLUDED.input_snapshot,
                    reason          = EXCLUDED.reason
            """,
                p,
            )
            # Append to history at most once per hour — prevents rapid /predict
            # calls from flooding the table and corrupting 7-day velocity logic.
            cur.execute(
                """
                INSERT INTO prediction_history
                    (student_id, readiness_score, category, recorded_at, assessment_type, model_version, input_snapshot, reason)
                SELECT %(sid)s, %(score)s, %(cat)s, NOW(), %(type)s, %(ver)s, %(snap)s::jsonb, %(reason)s
                WHERE NOT EXISTS (
                    SELECT 1 FROM prediction_history
                    WHERE  student_id = %(sid)s
                      AND  recorded_at > NOW() - INTERVAL '1 hour'
                )
            """,
                p,
            )


if __name__ == "__main__":
    # Predict for all 8 students and print results
    for sid in range(1, 9):
        result = predict(sid)
        print(
            f"Student {sid:2d} → {result['assessment_type']}  score: {result['readiness_score']}  "
            f"category: {result['category']}  model: {result['model_version']}"
        )
