from fastapi     import APIRouter, Depends, HTTPException
from app.auth    import require_operator
from app.schemas import FeatureResponse
from ingest.db_connection import get_connection

router = APIRouter(tags=["Features"], dependencies=[Depends(require_operator)])

@router.get("/{student_id}", response_model=FeatureResponse)
def get_features(student_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM features WHERE student_id = %s", (student_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"No features for student {student_id}. Run features/compute.py first."
                )
            cols = [desc[0] for desc in cur.description]
            return dict(zip(cols, row))
