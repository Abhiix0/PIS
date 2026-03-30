from fastapi         import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm  import Session
from sqlalchemy      import text
from app.db          import get_db
from app.schemas     import InsightResponse, RankingItem
from insights.engine import InsightEngine

router  = APIRouter(tags=["Insights"])
_engine = InsightEngine()  # instantiate once at module load

@router.get("/insights/{student_id}", response_model=InsightResponse)
def get_insights(student_id: int, db: Session = Depends(get_db)):
    # Confirm student exists
    row = db.execute(
        text("SELECT id FROM students WHERE id = :id"),
        {"id": student_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")
    try:
        result = _engine.format_insight(student_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insight generation failed: {e}")

@router.get("/ranking", response_model=list[RankingItem])
def get_ranking(
    db:     Session = Depends(get_db),
    branch: str     = Query(None, description="Filter by branch e.g. CSE"),
    limit:  int     = Query(10,  ge=1, le=100),
):
    sql = text("""
        WITH scored AS (
            SELECT s.id, s.name, s.branch, s.cgpa,
                   f.total_problems, f.consistency_score,
                   f.avg_difficulty, f.commit_frequency,
                   ROUND((s.cgpa*10 + f.total_problems*0.2 +
                          f.avg_difficulty*5 + f.consistency_score*20 +
                          f.commit_frequency*15)::NUMERIC, 2) AS composite_score
            FROM students s JOIN features f ON s.id = f.student_id
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
        WHERE (:branch IS NULL OR branch = :branch)
        ORDER BY global_rank
        LIMIT :limit
    """)
    rows = db.execute(sql, {"branch": branch, "limit": limit}).fetchall()
    return [dict(r._mapping) for r in rows]