from fastapi      import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy     import text
from app.db        import get_db
from app.schemas   import PredictionResponse
from ml.predict    import predict
from features.compute import run_feature_sql

router = APIRouter(tags=["Predictions"])

@router.post("/predict/{student_id}", response_model=PredictionResponse)
def run_prediction(student_id: int, db: Session = Depends(get_db)):
    # Confirm student exists before running the pipeline
    row = db.execute(
        text("SELECT id FROM students WHERE id = :id"),
        {"id": student_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")
    try:
        # Re-compute features before predicting — ensures freshness
        run_feature_sql()
        result = predict(student_id)
        return {
            "student_id":      student_id,
            "readiness_score": result["readiness_score"],
            "category":        result["category"],
            "last_updated":    result["predicted_at"],
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")

@router.get("/prediction/{student_id}", response_model=PredictionResponse)
def get_prediction(student_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT * FROM predictions WHERE student_id = :id"),
        {"id": student_id}
    ).fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No prediction for student {student_id}. Run POST /predict/{student_id} first."
        )
    return dict(row._mapping)