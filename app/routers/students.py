from fastapi     import APIRouter, HTTPException
from app.schemas import StudentCreate, StudentResponse, StudentListItem, StudentStatus, PredictionHistoryItem, StudentUpdate
from ingest.db_connection import get_connection

router = APIRouter(prefix="/students", tags=["Students"])

@router.post("", response_model=StudentResponse, status_code=201)
def create_student(body: StudentCreate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM students WHERE email = %s", (body.email,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=409,
                    detail=f"Student with email {body.email} already exists"
                )
            d = body.model_dump()
            cur.execute("""
                INSERT INTO students (name, email, cgpa, branch, github_username, leetcode_username)
                VALUES (%(name)s, %(email)s, %(cgpa)s, %(branch)s, %(github_username)s, %(leetcode_username)s)
                RETURNING id, name, email, cgpa, branch, github_username, leetcode_username, created_at
            """, d)
            row = cur.fetchone()
            cols = [desc[0] for desc in cur.description]
            return dict(zip(cols, row))


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(student_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM students WHERE id = %s", (student_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Student {student_id} not found")
            cols = [desc[0] for desc in cur.description]
            return dict(zip(cols, row))


@router.get("", response_model=list[StudentListItem])
def list_students():
    """List all students with their current prediction status."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.id, s.name, s.email, s.branch, s.cgpa,
                       p.readiness_score,
                       p.category,
                       CASE WHEN p.student_id IS NOT NULL THEN true ELSE false END AS has_prediction
                FROM   students s
                LEFT JOIN predictions p ON s.id = p.student_id
                ORDER BY s.id
            """)
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, r)) for r in rows]


@router.get("/{student_id}/status", response_model=StudentStatus)
def get_student_status(student_id: int):
    """Get a student's current pipeline status.

    pipeline_stage values:
      'no_data'           — student exists but no activity ingested
      'features_computed' — features computed but no prediction yet
      'predicted'         — prediction exists
      'complete'          — prediction + insight both available
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.id, s.name, s.branch, s.cgpa,
                       s.github_username, s.leetcode_username,
                       f.computed_at        AS features_computed_at,
                       p.readiness_score,
                       p.category,
                       p.last_updated       AS prediction_updated
                FROM   students s
                LEFT JOIN features    f ON s.id = f.student_id
                LEFT JOIN predictions p ON s.id = p.student_id
                WHERE  s.id = %s
            """, (student_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Student {student_id} not found")
            cols = [desc[0] for desc in cur.description]
            d = dict(zip(cols, row))

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
def get_student_history(student_id: int):
    """Return the last 30 prediction history records for a student."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM students WHERE id = %s", (student_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

            cur.execute("""
                SELECT readiness_score, category, recorded_at
                FROM   prediction_history
                WHERE  student_id = %s
                ORDER  BY recorded_at DESC
                LIMIT  30
            """, (student_id,))
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, r)) for r in rows]


@router.patch("/{student_id}", response_model=StudentResponse)
def update_student(student_id: int, body: StudentUpdate):
    """Update a student's platform usernames and/or CGPA.
    Only the fields provided in the request body are updated.
    Email and branch cannot be changed after creation.
    """
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=422, detail="No fields provided to update.")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM students WHERE id = %s", (student_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

            set_clauses = ", ".join(f"{col} = %({col})s" for col in updates)
            params = {**updates, "id": student_id}
            cur.execute(f"UPDATE students SET {set_clauses} WHERE id = %(id)s", params)

            cur.execute("SELECT * FROM students WHERE id = %s", (student_id,))
            row = cur.fetchone()
            cols = [desc[0] for desc in cur.description]
            return dict(zip(cols, row))
