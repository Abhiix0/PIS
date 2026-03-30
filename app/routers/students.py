from fastapi      import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
# ENSURED 'text' is imported here
from sqlalchemy import text
from app.db         import get_db
from app.schemas   import StudentCreate, StudentResponse

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
            INSERT INTO students (name, email, cgpa, branch)
            VALUES (:name, :email, :cgpa, :branch)
            RETURNING id, name, email, cgpa, branch, created_at
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