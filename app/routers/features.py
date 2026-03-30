# ADDED APIRouter to imports
from fastapi      import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy     import text
from app.db         import get_db
from app.schemas   import FeatureResponse

router = APIRouter(tags=["Features"])

@router.get("/{student_id}", response_model=FeatureResponse)
def get_features(student_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT * FROM features WHERE student_id = :id"),
        {"id": student_id}
    ).fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No features for student {student_id}. Run features/compute.py first."
        )
    return dict(row._mapping)