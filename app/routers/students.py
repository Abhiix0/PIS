from fastapi        import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy     import text
from app.db         import get_db
from app.schemas    import StudentCreate, StudentResponse, StudentListItem, StudentStatus, PredictionHistoryItem, StudentUpdate

router = APIRouter(prefix="/students", tags=["Students"])

@router.post("", response_model=StudentResponse, status_code=201)
def create_student(body: StudentCreate, db: Session = Depends(get_db)):
    existing = db.execute(
        text("SELECT id FROM students WHERE email = :email"),
        {"email": body.email}
    ).fetchone()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Student with email {body.email} already exists"
        )
    row = db.execute(
        text("""
            INSERT INTO students (name, email, cgpa, branch, github_username, leetcode_username)
            VALUES (:name, :email, :cgpa, :branch, :github_username, :leetcode_username)
            RETURNING id, name, email, cgpa, branch, github_username, leetcode_username, created_at
        """),
        body.model_dump()
    ).fetchone()
    db.commit()
    return dict(row._mapping)

@router.get("/{student_id}", response_model=StudentResponse)
def get_student(student_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT * FROM students WHERE id = :id"),
        {"id": student_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")
    return dict(row._mapping)


@router.get("", response_model=list[StudentListItem])
def list_students(db: Session = Depends(get_db)):
    """List all students with their current prediction status."""
    rows = db.execute(text("""
        SELECT s.id, s.name, s.email, s.branch, s.cgpa,
               p.readiness_score,
               p.category,
               CASE WHEN p.student_id IS NOT NULL THEN true ELSE false END AS has_prediction
        FROM   students s
        LEFT JOIN predictions p ON s.id = p.student_id
        ORDER BY s.id
    """)).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/{student_id}/status", response_model=StudentStatus)
def get_student_status(student_id: int, db: Session = Depends(get_db)):
    """Get a student's current pipeline status.

    pipeline_stage values:
      'no_data'           — student exists but no activity ingested
      'features_computed' — features computed but no prediction yet
      'predicted'         — prediction exists
      'complete'          — prediction + insight both available
    """
    row = db.execute(text("""
        SELECT s.id, s.name, s.branch, s.cgpa,
               s.github_username, s.leetcode_username,
               f.computed_at        AS features_computed_at,
               p.readiness_score,
               p.category,
               p.last_updated       AS prediction_updated
        FROM   students s
        LEFT JOIN features    f ON s.id = f.student_id
        LEFT JOIN predictions p ON s.id = p.student_id
        WHERE  s.id = :id
    """), {"id": student_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

    d = dict(row._mapping)
    features_computed = d.get("features_computed_at") is not None
    prediction_exists = d.get("readiness_score") is not None

    if prediction_exists:
        stage = "complete"
    elif features_computed:
        stage = "features_computed"
    else:
        stage = "no_data"

    return {
        "student_id":           student_id,
        "name":                 d["name"],
        "branch":               d["branch"],
        "cgpa":                 float(d["cgpa"]),
        "github_username":      d.get("github_username"),
        "leetcode_username":    d.get("leetcode_username"),
        "features_computed":    features_computed,
        "features_computed_at": d.get("features_computed_at"),
        "prediction_exists":    prediction_exists,
        "readiness_score":      float(d["readiness_score"]) if d.get("readiness_score") else None,
        "category":             d.get("category"),
        "prediction_updated":   d.get("prediction_updated"),
        "pipeline_stage":       stage,
    }


@router.get("/{student_id}/history", response_model=list[PredictionHistoryItem])
def get_student_history(student_id: int, db: Session = Depends(get_db)):
    """Return the last 30 prediction history records for a student."""
    row = db.execute(
        text("SELECT id FROM students WHERE id = :id"), {"id": student_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

    rows = db.execute(text("""
        SELECT readiness_score, category, recorded_at
        FROM   prediction_history
        WHERE  student_id = :id
        ORDER  BY recorded_at DESC
        LIMIT  30
    """), {"id": student_id}).fetchall()
    return [dict(r._mapping) for r in rows]


@router.patch("/{student_id}", response_model=StudentResponse)
def update_student(
    student_id: int,
    body:       StudentUpdate,
    db:         Session = Depends(get_db),
):
    """Update a student's platform usernames and/or CGPA.
    Only the fields provided in the request body are updated.
    Email and branch cannot be changed after creation.
    """
    existing = db.execute(
        text("SELECT id FROM students WHERE id = :id"),
        {"id": student_id}
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=422, detail="No fields provided to update.")

    set_clauses = ", ".join(f"{col} = :{col}" for col in updates)
    params = {**updates, "id": student_id}
    db.execute(text(f"UPDATE students SET {set_clauses} WHERE id = :id"), params)
    db.commit()

    row = db.execute(
        text("SELECT * FROM students WHERE id = :id"),
        {"id": student_id}
    ).fetchone()
    return dict(row._mapping)
