from app.logger import logger
from fastapi      import APIRouter, Depends, HTTPException
from app.auth     import require_operator, expensive
from app.schemas  import PredictionResponse
from ingest.db_connection import get_connection
from ml.predict   import predict
from features.compute import run_feature_sql

router = APIRouter(tags=["Predictions"], dependencies=[Depends(require_operator)])

@router.post("/predict/{student_id}", response_model=PredictionResponse, dependencies=[Depends(expensive)])
def run_prediction(student_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM students WHERE id = %s", (student_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail=f"Student {student_id} not found")
    try:
        run_feature_sql()
        result = predict(student_id)
        return {
            "student_id":      student_id,
            "assessment_type": result["assessment_type"],
            "readiness_score": result["readiness_score"],
            "category":        result["category"],
            "reason":          result["reason"],
            "model_version":   result["model_version"],
            "last_updated":    result["predicted_at"],
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("predictions failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/prediction/{student_id}", response_model=PredictionResponse)
def get_prediction(student_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM predictions WHERE student_id = %s", (student_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"No prediction for student {student_id}. Run POST /predict/{student_id} first."
                )
            cols = [desc[0] for desc in cur.description]
            return dict(zip(cols, row))
