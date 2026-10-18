from fastapi import APIRouter, Depends, HTTPException

from app.auth import expensive, require_operator
from app.logger import logger
from app.schemas import IngestResponse
from ingest.coding import ingest_coding_activity
from ingest.db_connection import get_connection
from ingest.github import ingest_github_activity
from ingest.github_api import fetch_github_data
from ingest.provider import ProviderError

router = APIRouter(
    prefix="/ingest",
    tags=["Ingestion"],
    dependencies=[Depends(require_operator), Depends(expensive)],
)


@router.post("/coding/real/{student_id}", response_model=IngestResponse)
def ingest_coding_real(student_id: int):
    """Removed in Phase 6: the old path invented per-problem rows and solve dates from aggregate counts."""
    raise HTTPException(
        status_code=501,
        detail="Real LeetCode ingestion is unavailable for legacy students: only solved-count aggregates are "
        "observable. Real users use POST /integrations/leetcode/sync (disabled by default).",
    )


@router.post("/coding/{student_id}", response_model=IngestResponse)
def ingest_coding(student_id: int):
    try:
        result = ingest_coding_activity(student_id=student_id)
        return IngestResponse(
            student_id=student_id,
            inserted=result["inserted"],
            skipped=result["skipped"],
            message=f"Coding ingestion complete for student {student_id}",
            data_source="synthetic",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    except Exception:
        logger.exception("ingest failed")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.post("/github/real/{student_id}", response_model=IngestResponse)
def ingest_github_real(student_id: int):
    """Fetch real GitHub data for a student using their github_username."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, github_username FROM students WHERE id = %s", (student_id,))
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

    github_username = row[1]
    if not github_username:
        raise HTTPException(
            status_code=422,
            detail=f"Student {student_id} has no github_username set. "
            f"Update student profile first.",
        )

    try:
        records = fetch_github_data(github_username)
    except ProviderError as e:
        raise HTTPException(
            status_code=422 if e.code == "not_found" else 503,
            detail=f"GitHub lookup failed: {e.code}",
        ) from None
    except Exception:
        logger.exception("ingest failed")
        raise HTTPException(status_code=500, detail="Internal server error") from None

    if not records:
        return IngestResponse(
            student_id=student_id,
            inserted=0,
            skipped=0,
            message=f"No public repositories found for GitHub user '{github_username}'",
            data_source="real_github_api",
        )

    total_inserted = 0
    total_skipped = 0

    with get_connection() as conn:
        with conn.cursor() as cur:
            for record in records:
                cur.execute(
                    """
                    INSERT INTO github_activity (student_id, repo_name, commits, commit_date, provenance)
                    VALUES (%(student_id)s, %(repo_name)s, %(commits)s, %(commit_date)s, 'observed')
                    ON CONFLICT (student_id, repo_name, commit_date) DO NOTHING
                """,
                    {**record, "student_id": student_id},
                )
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
        data_source="real_github_api",
    )


@router.post("/github/{student_id}", response_model=IngestResponse)
def ingest_github(student_id: int):
    try:
        result = ingest_github_activity(student_id=student_id)
        return IngestResponse(
            student_id=student_id,
            inserted=result["inserted"],
            skipped=result["skipped"],
            message=f"GitHub ingestion complete for student {student_id}",
            data_source="synthetic",
        )
    except Exception:
        logger.exception("ingest failed")
        raise HTTPException(status_code=500, detail="Internal server error") from None
