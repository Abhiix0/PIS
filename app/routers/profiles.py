from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import Principal, current_principal
from ingest.db_connection import get_connection

router = APIRouter(tags=["Profiles"])

_COLS = "id::text AS id, display_name, branch, graduation_year, cgpa::float AS cgpa, created_at"


class ProfileIn(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)
    branch: str | None = Field(None, max_length=50)
    graduation_year: int | None = Field(None, ge=2000, le=2100)
    cgpa: float | None = Field(None, ge=0, le=10)


class ProfilePatch(ProfileIn):
    display_name: str | None = Field(None, min_length=1, max_length=100)  # type: ignore[assignment]  # PATCH loosens the required parent field


def _row(cur):
    cols = [d[0] for d in cur.description]
    r = cur.fetchone()
    return dict(zip(cols, r)) if r else None


@router.get("/me")
def me(p: Principal = Depends(current_principal)):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id::text FROM profiles WHERE user_id = %s", (p.user_id,))
        row = cur.fetchone()
    return {
        "user_id": p.user_id,
        "profile_id": row[0] if row else None,
        "is_operator": p.is_operator,
    }


@router.post("/auth/logout", status_code=204)
def logout(p: Principal = Depends(current_principal)):
    """Revoke every token issued to this user up to now."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET sessions_valid_after = now(), updated_at = now() WHERE id = %s",
            (p.user_id,),
        )


@router.post("/profiles", status_code=201)
def create_profile(body: ProfileIn, p: Principal = Depends(current_principal)):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO profiles (user_id, origin, display_name, branch, graduation_year, cgpa) "
            "VALUES (%s, 'real', %s, %s, %s, %s) ON CONFLICT (user_id) DO NOTHING RETURNING "
            + _COLS,
            (p.user_id, body.display_name, body.branch, body.graduation_year, body.cgpa),
        )
        row = _row(cur)
    if not row:
        raise HTTPException(status_code=409, detail="Profile already exists")
    return row


# Ownership is enforced in the query itself: a profile that is not yours looks the same as one that does not exist.
@router.get("/profiles/{profile_id}")
def get_profile(profile_id: str, p: Principal = Depends(current_principal)):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT {_COLS} FROM profiles WHERE id::text = %s AND user_id = %s",
            (profile_id, p.user_id),
        )
        row = _row(cur)
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
    return row


@router.patch("/profiles/{profile_id}")
def update_profile(profile_id: str, body: ProfilePatch, p: Principal = Depends(current_principal)):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=422, detail="No fields provided to update.")
    sets = ", ".join(
        f"{c} = %({c})s" for c in updates
    )  # column names come from the model, never the client
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE profiles SET {sets}, updated_at = now() WHERE id::text = %(pid)s AND user_id = %(uid)s "
            f"RETURNING {_COLS}",
            {**updates, "pid": profile_id, "uid": p.user_id},
        )
        row = _row(cur)
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
    return row
