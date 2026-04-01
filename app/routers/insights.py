import os
from fastapi         import APIRouter, HTTPException, Query
from app.schemas     import InsightResponse, RankingItem
from ingest.db_connection import get_connection
from insights.engine import InsightEngine

router = APIRouter(tags=["Insights"])

_IMPORTANCES_PATH = "models/feature_importances.json"
_engine: InsightEngine | None = None
_engine_mtime: float = 0.0


def _get_engine() -> InsightEngine:
    """Return the InsightEngine, reloading it if feature_importances.json
    has been updated since last instantiation (e.g. after ml/train.py runs).
    """
    global _engine, _engine_mtime
    try:
        current_mtime = os.path.getmtime(_IMPORTANCES_PATH)
    except FileNotFoundError:
        current_mtime = 0.0
    if _engine is None or current_mtime > _engine_mtime:
        _engine = InsightEngine()
        _engine_mtime = current_mtime
    return _engine


@router.get("/insights/{student_id}", response_model=InsightResponse)
def get_insights(student_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM students WHERE id = %s", (student_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail=f"Student {student_id} not found")
    try:
        result = _get_engine().format_insight(student_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insight generation failed: {e}")


@router.get("/ranking", response_model=list[RankingItem])
def get_ranking(
    branch: str = Query(None, description="Filter by branch e.g. CSE"),
    limit:  int = Query(10, ge=1, le=100),
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                WITH scored AS (
                    SELECT s.id, s.name, s.branch, s.cgpa,
                           f.total_problems, f.consistency_score,
                           f.avg_difficulty, f.commit_frequency,
                           p.readiness_score AS composite_score
                    FROM students s
                    JOIN features    f ON s.id = f.student_id
                    JOIN predictions p ON s.id = p.student_id
                ),
                ranked AS (
                    SELECT *,
                        RANK() OVER (ORDER BY composite_score DESC) AS global_rank,
                        RANK() OVER (PARTITION BY branch ORDER BY composite_score DESC) AS branch_rank,
                        ROUND(100.0*(1-(RANK() OVER (ORDER BY composite_score DESC)-1)
                            ::NUMERIC/COUNT(*) OVER()), 1) AS percentile
                    FROM scored
                )
                SELECT * FROM ranked
                WHERE (%s IS NULL OR branch = %s)
                ORDER BY global_rank
                LIMIT %s
            """, (branch, branch, limit))
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, r)) for r in rows]
