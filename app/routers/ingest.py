from fastapi        import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy     import text
from datetime       import date, timedelta
import random
from app.schemas       import IngestResponse
from app.db            import get_db
from ingest.coding     import ingest_coding_activity
from ingest.github     import ingest_github_activity
from ingest.github_api import fetch_github_data
from ingest.leetcode_api import fetch_leetcode_data

router = APIRouter(prefix="/ingest", tags=["Ingestion"])

@router.post("/coding/real/{student_id}", response_model=IngestResponse)
def ingest_coding_real(
    student_id:    int,
    db:            Session = Depends(get_db),
    force_refresh: bool    = Query(False, description="Bypass 24h cache and re-fetch from LeetCode API"),
):
    """Fetch real LeetCode data for a student using their leetcode_username.

    Falls back to synthetic generation if:
    - leetcode_username is not set on the student
    - LeetCode API is unavailable
    - Username is not found or profile is private
    """
    from ingest.db_connection import get_connection, clear_coding_activity
    from ingest.validators import validate_coding_record

    row = db.execute(
        text("SELECT id, leetcode_username FROM students WHERE id = :id"),
        {"id": student_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

    leetcode_username = row._mapping.get("leetcode_username")
    data_source = "synthetic"
    records = []

    # Try real API if username is set
    if leetcode_username:
        try:
            raw_records, data_source = fetch_leetcode_data(leetcode_username)
            if raw_records:
                records = raw_records
                print(f"[LeetCode] Fetched {len(records)} records for '{leetcode_username}'")
            else:
                print(f"[LeetCode] No solved problems found for "
                      f"'{leetcode_username}', falling back to synthetic")
                data_source = "synthetic"
        except ValueError as e:
            print(f"[LeetCode] Username error: {e}. Falling back to synthetic.")
        except RuntimeError as e:
            print(f"[LeetCode] API error: {e}. Falling back to synthetic.")
        except Exception as e:
            print(f"[LeetCode] Unexpected error: {e}. Falling back to synthetic.")

    # Fallback to synthetic if no real data
    if not records:
        from ingest.coding import generate_coding_records, STUDENT_PROFILES
        data_source = "synthetic"
        if student_id in STUDENT_PROFILES:
            records = generate_coding_records(student_id)
        else:
            # Default profile for new students not in STUDENT_PROFILES
            start_date = date.today() - timedelta(days=180)
            for i in range(30):  # default: 30 medium problems
                records.append({
                    "student_id": student_id,
                    "problem_id": f"P{student_id:02d}{i+1:04d}",
                    "difficulty": "medium",
                    "solved_at":  start_date + timedelta(days=random.randint(0, 180)),
                })

    # Insert records — clear first if using real data OR force_refresh requested
    total_inserted = 0
    total_skipped  = 0

    if (data_source == "real_leetcode_stats" or force_refresh) and records:
        clear_coding_activity(student_id)
        print(f"[DEBUG] Inserting {len(records)} fresh records for student {student_id}")

    with get_connection() as conn:
        cur = conn.cursor()
        for record in records:
            full_record = {
                "student_id": student_id,
                "problem_id": record.get("problem_id", ""),
                "difficulty": record.get("difficulty", "medium"),
                "solved_at":  record.get("solved_at", date.today()),
            }
            try:
                validate_coding_record(full_record)
            except ValueError:
                total_skipped += 1
                continue

            cur.execute("""
                INSERT INTO coding_activity
                    (student_id, problem_id, difficulty, solved_at)
                VALUES
                    (%(student_id)s, %(problem_id)s, %(difficulty)s, %(solved_at)s)
                ON CONFLICT (student_id, problem_id) DO NOTHING
            """, full_record)

            if cur.rowcount == 1:
                total_inserted += 1
            else:
                total_skipped += 1

    return IngestResponse(
        student_id=student_id,
        inserted=total_inserted,
        skipped=total_skipped,
        message=f"Coding ingestion complete (source: {data_source})",
        data_source=data_source,
    )


@router.post("/coding/{student_id}", response_model=IngestResponse)
def ingest_coding(student_id: int):
    try:
        result = ingest_coding_activity(student_id=student_id)
        return IngestResponse(
            student_id=student_id,
            inserted=result['inserted'],
            skipped=result['skipped'],
            message=f"Coding ingestion complete for student {student_id}",
            data_source="synthetic"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

@router.post("/github/real/{student_id}", response_model=IngestResponse)
def ingest_github_real(student_id: int, db: Session = Depends(get_db)):
    """Fetch real GitHub data for a student using their github_username.

    Requires the student to have github_username set.
    Uses GitHub REST API (rate limit: 60/hr without token, 5000/hr with GITHUB_TOKEN).
    """
    row = db.execute(
        text("SELECT id, github_username FROM students WHERE id = :id"),
        {"id": student_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

    github_username = row._mapping.get("github_username")
    if not github_username:
        raise HTTPException(
            status_code=422,
            detail=f"Student {student_id} has no github_username set. "
                   f"Update student profile first."
        )

    try:
        records = fetch_github_data(github_username)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GitHub API error: {type(e).__name__}: {e}")

    if not records:
        return IngestResponse(
            student_id=student_id,
            inserted=0,
            skipped=0,
            message=f"No public repositories found for GitHub user '{github_username}'",
            data_source="real_github_api"
        )

    from ingest.db_connection import get_connection
    total_inserted = 0
    total_skipped  = 0

    with get_connection() as conn:
        cur = conn.cursor()
        for record in records:
            cur.execute("""
                INSERT INTO github_activity (student_id, repo_name, commits, commit_date)
                VALUES (%(student_id)s, %(repo_name)s, %(commits)s, %(commit_date)s)
                ON CONFLICT (student_id, repo_name, commit_date) DO NOTHING
            """, {**record, "student_id": student_id})
            if cur.rowcount == 1:
                total_inserted += 1
            else:
                total_skipped += 1

    return IngestResponse(
        student_id=student_id,
        inserted=total_inserted,
        skipped=total_skipped,
        message=f"Real GitHub data ingested for '{github_username}': "
                f"{len(records)} repos processed",
        data_source="real_github_api"
    )


@router.post("/github/{student_id}", response_model=IngestResponse)
def ingest_github(student_id: int):
    try:
        result = ingest_github_activity(student_id=student_id)
        return IngestResponse(
            student_id=student_id,
            inserted=result['inserted'],
            skipped=result['skipped'],
            message=f"GitHub ingestion complete for student {student_id}",
            data_source="synthetic"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")