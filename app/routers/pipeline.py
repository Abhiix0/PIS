from fastapi         import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm  import Session
from sqlalchemy      import text
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.db          import get_db
from app.schemas     import PipelineResponse, BatchPipelineRequest
from services.pipeline import run as run_pipeline

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


@router.post("/batch", response_model=list[PipelineResponse])
def run_batch_pipeline(body: BatchPipelineRequest, db: Session = Depends(get_db)):
    """Run the full pipeline for multiple students.

    Processes up to 3 students concurrently.
    Maximum 20 students per batch request.
    Individual student failures do not stop the batch.
    """
    results_map: dict = {}

    def _run_one(student_id: int):
        try:
            return student_id, run_pipeline(student_id)
        except Exception as e:
            return student_id, {
                "student_id":        student_id,
                "student_name":      f"Student {student_id}",
                "readiness_score":   None,
                "category":          "Error",
                "strengths":         [],
                "weaknesses":        [],
                "composite_insights": [],
                "recommendations":   [],
                "top_priority":      f"Pipeline failed: {str(e)}",
                "pipeline_steps":    [],
                "total_duration_ms": 0,
                "ran_at":            "",
            }

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(_run_one, sid): sid for sid in body.student_ids}
        for future in as_completed(futures):
            sid, result = future.result()
            results_map[sid] = result

    # Return in original request order
    return [results_map[sid] for sid in body.student_ids]


@router.post("/{student_id}", response_model=PipelineResponse)
def run_full_pipeline(
    student_id:    int,
    db:            Session = Depends(get_db),
    force_refresh: bool    = Query(False, description="Bypass 24h cache and re-fetch from all APIs"),
):
    """Run the full PIS pipeline for a student in one call."""
    row = db.execute(
        text("SELECT id FROM students WHERE id = :id"),
        {"id": student_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

    try:
        result = run_pipeline(student_id, force_refresh=force_refresh)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {type(e).__name__}: {e}")
