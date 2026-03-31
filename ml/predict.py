import joblib
import pandas as pd
from pathlib  import Path
from datetime import datetime
from ingest.db_connection import get_connection

FEATURE_COLS = [
    'cgpa', 'total_problems', 'avg_difficulty',
    'consistency_score', 'commit_frequency'
]

# Load models once at module level — not on every prediction call
_regressor  = joblib.load(Path('models/regressor.pkl'))
_classifier = joblib.load(Path('models/classifier.pkl'))
_scaler     = joblib.load(Path('models/scaler.pkl'))

def _fetch_scaled_features(student_id: int) -> pd.DataFrame:
    """Pull this student's scaled features from the DB.
    Applies the same Min-Max scaling used in Phase 3
    by reading from features_scaled.csv as reference.
    """
    query = """
        SELECT
            s.cgpa,
            f.total_problems,
            f.avg_difficulty,
            f.consistency_score,
            f.commit_frequency
        FROM  students s
        JOIN  features  f ON s.id = f.student_id
        WHERE s.id = %(student_id)s
    """
    with get_connection() as conn:
        df = pd.read_sql(query, conn, params={'student_id': student_id})

    if df.empty:
        raise ValueError(f"No features found for student_id={student_id}. "
                         "Run features/compute.py first.")

    # Scale using the fitted scaler saved during feature computation
    df[FEATURE_COLS] = _scaler.transform(df[FEATURE_COLS])
    df[FEATURE_COLS] = df[FEATURE_COLS].clip(0.0, 1.0)  # guard against out-of-range real data
    return df[FEATURE_COLS]

def predict(student_id: int) -> dict:
    """Run both models for a student and save result to predictions table.

    Returns:
        dict with student_id, readiness_score, category, predicted_at
    """
    features = _fetch_scaled_features(student_id)

    score    = round(float(_regressor.predict(features)[0]), 2)
    # Clamp to valid range — float precision can give 100.0001
    score    = max(0.0, min(100.0, score))
    category = str(_classifier.predict(features)[0])

    _save_prediction(student_id, score, category)

    return {
        'student_id':     student_id,
        'readiness_score': score,
        'category':        category,
        'predicted_at':    datetime.utcnow().isoformat(),
    }

def _save_prediction(student_id: int, score: float, category: str):
    """Upsert prediction into DB."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO predictions
                    (student_id, readiness_score, category, last_updated)
                VALUES
                    (%(sid)s, %(score)s, %(cat)s, NOW())
                ON CONFLICT (student_id) DO UPDATE SET
                    readiness_score = EXCLUDED.readiness_score,
                    category        = EXCLUDED.category,
                    last_updated    = NOW()
            """, {'sid': student_id, 'score': score, 'cat': category})

if __name__ == "__main__":
    # Predict for all 8 students and print results
    for sid in range(1, 9):
        result = predict(sid)
        print(f"Student {sid:2d} → score: {result['readiness_score']:6.2f}  "
              f"category: {result['category']}")