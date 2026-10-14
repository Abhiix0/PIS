"""Pipeline orchestration module.

Runs the full PIS pipeline for a student in sequence:
1. Ingest coding activity (real if leetcode_username set, else synthetic)
2. Ingest GitHub activity (real if github_username set, else synthetic)
3. Compute features (run SQL CTE pipeline)
4. Run ML prediction
5. Generate insights

This module contains the business logic.
The router only handles HTTP concerns.
"""

import time
import psycopg2
from datetime import datetime, date, timezone, timedelta
from config import DATABASE_URL

# Real API calls are skipped if data was synced within this window.
# Prevents hammering GitHub/LeetCode on every pipeline call.
_SYNC_TTL_HOURS = 24


def _is_fresh(last_synced) -> bool:
    """Return True if last_synced is within the TTL window."""
    if last_synced is None:
        return False
    # last_synced may be a tz-aware or tz-naive datetime depending on the driver
    now = datetime.now(timezone.utc)
    if last_synced.tzinfo is None:
        last_synced = last_synced.replace(tzinfo=timezone.utc)
    return (now - last_synced) < timedelta(hours=_SYNC_TTL_HOURS)


def _get_student_usernames(student_id: int) -> dict:
    """Fetch usernames and last-sync timestamps for a student."""
    from ingest.db_connection import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT github_username, leetcode_username,
                          github_last_synced, leetcode_last_synced
                   FROM students WHERE id = %s""",
                (student_id,)
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Student {student_id} not found")
            return {
                "github_username":      row[0],
                "leetcode_username":    row[1],
                "github_last_synced":   row[2],
                "leetcode_last_synced": row[3],
            }


def _mark_synced(student_id: int, platform: str):
    """Stamp github_last_synced or leetcode_last_synced with NOW()."""
    col = "github_last_synced" if platform == "github" else "leetcode_last_synced"
    from ingest.db_connection import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE students SET {col} = NOW() WHERE id = %s",
                (student_id,)
            )


def run(student_id: int, force_refresh: bool = False) -> dict:
    """Run the full pipeline for one student.

    Returns a dict containing:
    - All fields from InsightEngine.format_insight()
    - pipeline_steps: list of step results with timing
    - total_duration_ms: total wall time
    - ran_at: ISO timestamp
    """
    start_time = time.perf_counter()
    steps = []

    usernames = _get_student_usernames(student_id)

    # ── Step 1: Coding ingestion ──────────────────────────────────────
    # Synthetic data is only generated for students with no username (labelled demo records). A student with a
    # LeetCode username is never given invented per-problem rows: the API exposes aggregates only (Phase 6).
    step_start = time.perf_counter()
    try:
        if usernames.get("leetcode_username"):
            steps.append({
                "step":        "coding_ingestion",
                "status":      "skipped",
                "data_source": "none",
                "reason":      "LeetCode exposes solved-count aggregates only; the per-problem legacy table is left unchanged.",
                "duration_ms": round((time.perf_counter() - step_start) * 1000, 1),
            })
        else:
            from ingest.coding import ingest_coding_activity
            result = ingest_coding_activity(student_id=student_id)
            steps.append({
                "step":             "coding_ingestion",
                "status":           "success",
                "data_source":      "synthetic",
                "records_inserted": result.get("inserted", 0),
                "duration_ms":      round((time.perf_counter() - step_start) * 1000, 1),
            })
    except Exception as e:
        steps.append({
            "step":        "coding_ingestion",
            "status":      "error",
            "error":       str(e),
            "duration_ms": round((time.perf_counter() - step_start) * 1000, 1),
        })

    # ── Step 2: GitHub ingestion ──────────────────────────────────────
    # A failed fetch is reported and leaves existing rows alone; it never falls back to synthetic data.
    step_start = time.perf_counter()
    try:
        if usernames.get("github_username"):
            if _is_fresh(usernames.get("github_last_synced")) and not force_refresh:
                step = {"status": "success", "data_source": "cached", "records_inserted": 0}
            else:
                from ingest.github_api import fetch_github_data
                from ingest.provider import ProviderError
                try:
                    gh_records = fetch_github_data(usernames["github_username"])
                except ProviderError as e:
                    step = {"status": "error", "data_source": "real_github_api", "error": e.code}
                else:
                    from ingest.db_connection import get_connection
                    gh_inserted = 0
                    with get_connection() as conn:
                        cur = conn.cursor()
                        for r in gh_records:
                            cur.execute("""
                                INSERT INTO github_activity
                                    (student_id, repo_name, commits, commit_date, provenance)
                                VALUES
                                    (%(student_id)s, %(repo_name)s, %(commits)s, %(commit_date)s, 'observed')
                                ON CONFLICT (student_id, repo_name, commit_date) DO NOTHING
                            """, {"student_id": student_id, **r})
                            gh_inserted += cur.rowcount
                    _mark_synced(student_id, "github")
                    step = {"status": "success", "data_source": "real_github_api", "records_inserted": gh_inserted}
        else:
            from ingest.github import ingest_github_activity
            result = ingest_github_activity(student_id=student_id)
            step = {"status": "success", "data_source": "synthetic", "records_inserted": result.get("inserted", 0)}
        steps.append({"step": "github_ingestion", **step,
                      "duration_ms": round((time.perf_counter() - step_start) * 1000, 1)})
    except Exception as e:
        steps.append({
            "step":        "github_ingestion",
            "status":      "error",
            "error":       str(e),
            "duration_ms": round((time.perf_counter() - step_start) * 1000, 1),
        })

    # ── Step 3: Feature computation ───────────────────────────────────
    # Uses the parameterised single-student SQL variant — O(1) DB work,
    # not O(n_students) like the full-table version used by ml.train.
    step_start = time.perf_counter()
    try:
        from features.compute import run_feature_sql_for_student
        run_feature_sql_for_student(student_id)
        steps.append({
            "step":        "feature_computation",
            "status":      "success",
            "duration_ms": round((time.perf_counter() - step_start) * 1000, 1),
        })
    except Exception as e:
        steps.append({
            "step":        "feature_computation",
            "status":      "error",
            "error":       str(e),
            "duration_ms": round((time.perf_counter() - step_start) * 1000, 1),
        })
        raise RuntimeError(f"Feature computation failed: {e}")

    # ── Step 4: ML prediction ─────────────────────────────────────────
    step_start = time.perf_counter()
    try:
        from ml.predict import predict
        prediction = predict(student_id)
        steps.append({
            "step":             "ml_prediction",
            "status":           "success",
            "readiness_score":  prediction["readiness_score"],
            "category":         prediction["category"],
            "duration_ms":      round((time.perf_counter() - step_start) * 1000, 1),
        })
    except Exception as e:
        steps.append({
            "step":        "ml_prediction",
            "status":      "error",
            "error":       str(e),
            "duration_ms": round((time.perf_counter() - step_start) * 1000, 1),
        })
        raise RuntimeError(f"ML prediction failed: {e}")

    # ── Step 5: Insight generation ────────────────────────────────────
    step_start = time.perf_counter()
    try:
        from insights.engine import InsightEngine
        engine = InsightEngine()
        insight = engine.format_insight(student_id)
        steps.append({
            "step":             "insight_generation",
            "status":           "success",
            "weaknesses_found": len(insight.get("weaknesses", [])),
            "duration_ms":      round((time.perf_counter() - step_start) * 1000, 1),
        })
    except Exception as e:
        steps.append({
            "step":        "insight_generation",
            "status":      "error",
            "error":       str(e),
            "duration_ms": round((time.perf_counter() - step_start) * 1000, 1),
        })
        raise RuntimeError(f"Insight generation failed: {e}")

    total_ms = round((time.perf_counter() - start_time) * 1000, 1)

    return {
        **insight,
        "pipeline_steps":    steps,
        "total_duration_ms": total_ms,
        "ran_at":            datetime.utcnow().isoformat(),
    }
