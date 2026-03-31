from fastapi         import APIRouter, Depends, HTTPException
from sqlalchemy.orm  import Session
from sqlalchemy      import text
from app.db          import get_db
from app.schemas     import PipelineResponse, BatchPipelineRequest
from services.pipeline import run as run_pipeline

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


@router.post("/batch", response_model=list[PipelineResponse])
def run_batch_pipeline(body: BatchPipelineRequest, db: Session = Depends(get_db)):
    """Run the full pipeline for multiple students.

    Processes students sequentially (not parallel).
    Maximum 20 students per batch request.
    Individual student failures do not stop the batch —
    failed students are included in the response with error info.
    """
    results = []
    for student_id in body.student_ids:
        try:
            result = run_pipeline(student_id)
            results.append(result)
        except Exception as e:
            results.append({
                "student_id":        student_id,
                "student_name":      f"Student {student_id}",
                "readiness_score":   None,
                "category":          "Error",
                "strengths":         [],
                "weaknesses":        [],
                "recommendations":   [],
                "top_priority":      f"Pipeline failed: {str(e)}",
                "pipeline_steps":    [],
                "total_duration_ms": 0,
                "ran_at":            "",
            })
    return results


@router.post("/{student_id}", response_model=PipelineResponse)
def run_full_pipeline(student_id: int, db: Session = Depends(get_db)):
    """Run the full PIS pipeline for a student in one call.

    Steps executed in sequence:
    1. Ingest coding activity (real LeetCode API if leetcode_username set)
    2. Ingest GitHub activity (real GitHub API if github_username set)
    3. Compute features via SQL CTE pipeline
    4. Run ML prediction (Random Forest regressor + classifier)
    5. Generate insight report (rule + ML hybrid engine)

    Returns the full insight report plus pipeline metadata.
    """
    row = db.execute(
        text("SELECT id FROM students WHERE id = :id"),
        {"id": student_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

    try:
        result = run_pipeline(student_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {type(e).__name__}: {e}")
