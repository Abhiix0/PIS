from fastapi    import APIRouter, HTTPException
from app.schemas import IngestResponse
from ingest.coding  import ingest_coding_activity
from ingest.github  import ingest_github_activity

router = APIRouter(prefix="/ingest", tags=["Ingestion"])

@router.post("/coding/{student_id}", response_model=IngestResponse)
def ingest_coding(student_id: int):
    try:
        result = ingest_coding_activity(student_id=student_id)
        return IngestResponse(
            student_id=student_id,
            inserted=result['inserted'],
            skipped=result['skipped'],
            message=f"Coding ingestion complete for student {student_id}"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

@router.post("/github/{student_id}", response_model=IngestResponse)
def ingest_github(student_id: int):
    try:
        result = ingest_github_activity(student_id=student_id)
        return IngestResponse(
            student_id=student_id,
            inserted=result['inserted'],
            skipped=result['skipped'],
            message=f"GitHub ingestion complete for student {student_id}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")