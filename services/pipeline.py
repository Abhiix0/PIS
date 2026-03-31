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
from datetime import datetime, date
from config import DATABASE_URL


def _get_student_usernames(student_id: int) -> dict:
    """Fetch github_username and leetcode_username for a student."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT github_username, leetcode_username FROM students WHERE id = %s",
                (student_id,)
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Student {student_id} not found")
            return {
                "github_username":   row[0],
                "leetcode_username": row[1],
            }
    finally:
        conn.close()


def run(student_id: int) -> dict:
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
    step_start = time.perf_counter()
    try:
        if usernames.get("leetcode_username"):
            from ingest.leetcode_api import fetch_leetcode_data
            from ingest.db_connection import get_connection
            from ingest.validators import validate_coding_record
            try:
                records = fetch_leetcode_data(usernames["leetcode_username"])
                data_source = "real_leetcode_api"
            except Exception as e:
                print(f"[Pipeline] LeetCode API failed ({e}), using synthetic")
                from ingest.coding import generate_coding_records, STUDENT_PROFILES
                records = generate_coding_records(student_id) if student_id in STUDENT_PROFILES else []
                data_source = "synthetic"
        else:
            from ingest.coding import ingest_coding_activity
            result = ingest_coding_activity(student_id=student_id)
            data_source = "synthetic"
            records = None

        if records is not None:
            from ingest.db_connection import get_connection
            from ingest.validators import validate_coding_record
            inserted = 0
            with get_connection() as conn:
                cur = conn.cursor()
                for r in records:
                    rec = {"student_id": student_id, **r}
                    try:
                        validate_coding_record(rec)
                    except ValueError:
                        continue
                    cur.execute("""
                        INSERT INTO coding_activity
                            (student_id, problem_id, difficulty, solved_at)
                        VALUES
                            (%(student_id)s, %(problem_id)s, %(difficulty)s, %(solved_at)s)
                        ON CONFLICT (student_id, problem_id) DO NOTHING
                    """, rec)
                    if cur.rowcount == 1:
                        inserted += 1
            coding_result = {"inserted": inserted, "source": data_source}
        else:
            coding_result = {"inserted": result.get("inserted", 0), "source": data_source}

        steps.append({
            "step":             "coding_ingestion",
            "status":           "success",
            "data_source":      data_source,
            "records_inserted": coding_result["inserted"],
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
    step_start = time.perf_counter()
    try:
        if usernames.get("github_username"):
            from ingest.github_api import fetch_github_data
            try:
                gh_records = fetch_github_data(usernames["github_username"])
                gh_source = "real_github_api"
            except Exception as e:
                print(f"[Pipeline] GitHub API failed ({e}), using synthetic")
                from ingest.github import generate_github_records, GITHUB_PROFILES
                raw = generate_github_records(student_id) if student_id in GITHUB_PROFILES else []
                gh_records = [
                    {"repo_name": r["repo_name"], "commits": r["commits"], "commit_date": r["commit_date"]}
                    for r in raw
                ]
                gh_source = "synthetic"
        else:
            from ingest.github import ingest_github_activity
            result = ingest_github_activity(student_id=student_id)
            gh_records = None
            gh_source = "synthetic"

        gh_inserted = 0
        if gh_records is not None:
            from ingest.db_connection import get_connection
            with get_connection() as conn:
                cur = conn.cursor()
                for r in gh_records:
                    cur.execute("""
                        INSERT INTO github_activity
                            (student_id, repo_name, commits, commit_date)
                        VALUES
                            (%(student_id)s, %(repo_name)s, %(commits)s, %(commit_date)s)
                        ON CONFLICT (student_id, repo_name, commit_date) DO NOTHING
                    """, {"student_id": student_id, **r})
                    if cur.rowcount == 1:
                        gh_inserted += 1
        else:
            gh_inserted = result.get("inserted", 0)

        steps.append({
            "step":             "github_ingestion",
            "status":           "success",
            "data_source":      gh_source,
            "records_inserted": gh_inserted,
            "duration_ms":      round((time.perf_counter() - step_start) * 1000, 1),
        })
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
