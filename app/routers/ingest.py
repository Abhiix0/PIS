from fastapi      import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy   import text
from app.schemas  import IngestResponse
from app.db       import get_db
from ingest.coding     import ingest_coding_activity
from ingest.github     import ingest_github_activity
from ingest.github_api import fetch_github_data

router = APIRouter(prefix="/ingest", tags=["Ingestion"])

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