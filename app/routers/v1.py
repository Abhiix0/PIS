"""Stable client contract, mounted at /api/v1. Every query is scoped by the token's user_id in the SQL itself.

Errors use the envelope {"error": {"code", "message", "request_id"}} (see app/main.py). Timestamps are ISO 8601
with a +00:00 offset (the DB pool pins the session time zone to UTC).
"""

import json
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from app.auth import Principal, current_principal, expensive
from features.as_of import FEATURES_VERSION, activity_trend, features_as_of
from ingest.db_connection import fetch_all, get_connection
from services import privacy, sync

router = APIRouter(prefix="/api/v1")
session_router = APIRouter(tags=["Session"])  # unprefixed: the desktop client calls /auth/logout
Provider = Literal["github", "leetcode"]
EVIDENCE_VERSION = "evidence-v1"
NO_SCORE_REASON = (
    "No readiness proxy score for real accounts: the model's inputs (per-problem solve history, "
    "daily commit rate) cannot be derived from provider data without inventing values. "
    "This is an evidence summary only."
)
_MY_PROFILE = "SELECT id FROM profiles WHERE user_id = %s"


def _dicts(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _one(rows: list[dict], what: str) -> dict:
    if not rows:
        raise HTTPException(status_code=404, detail=f"{what} not found")
    return rows[0]


def _refused(e: sync.SyncRefused):
    headers = {"Retry-After": str(e.retry_after)} if e.retry_after else None
    raise HTTPException(status_code=e.status, detail=e.detail, headers=headers)


# ── Profile ────────────────────────────────────────────────────────────
class ProfileIn(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)
    branch: str | None = Field(None, max_length=50)
    graduation_year: int | None = Field(None, ge=2000, le=2100)
    cgpa: float | None = Field(None, ge=0, le=10)


_PROFILE = "id::text AS id, display_name, branch, graduation_year, cgpa::float AS cgpa, created_at, updated_at"


@router.get("/me", tags=["Profile"])
def me(p: Principal = Depends(current_principal)):
    rows = fetch_all(f"SELECT {_PROFILE} FROM profiles WHERE user_id = %s", (p.user_id,))
    return {
        "user_id": p.user_id,
        "is_operator": p.is_operator,
        "profile": rows[0] if rows else None,
    }


@router.put("/me/profile", tags=["Profile"])
def put_profile(body: ProfileIn, response: Response, p: Principal = Depends(current_principal)):
    """Create or replace the caller's profile (idempotent). 201 on first create, 200 afterwards."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO profiles (user_id, origin, display_name, branch, graduation_year, cgpa) "
            "VALUES (%s, 'real', %s, %s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET display_name = EXCLUDED.display_name, "
            "branch = EXCLUDED.branch, graduation_year = EXCLUDED.graduation_year, cgpa = EXCLUDED.cgpa, updated_at = now() "
            f"RETURNING {_PROFILE}, (xmax = 0) AS inserted",
            (p.user_id, body.display_name, body.branch, body.graduation_year, body.cgpa),
        )
        row = _dicts(cur)[0]
    response.status_code = 201 if row.pop("inserted") else 200
    return row


@session_router.post("/auth/logout", status_code=204)
def logout(p: Principal = Depends(current_principal)):
    """Revoke every token issued to this user up to now."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET sessions_valid_after = now(), updated_at = now() WHERE id = %s",
            (p.user_id,),
        )


# ── Integrations and sync ──────────────────────────────────────────────
class ConnectIn(BaseModel):
    username: str = Field(
        ..., min_length=1, max_length=64
    )  # public username only; no tokens are accepted


@router.get("/integrations", tags=["Integrations"])
def list_integrations(p: Principal = Depends(current_principal)):
    return {"items": sync.list_connections(p.user_id)}


@router.put("/integrations/{provider}", tags=["Integrations"])
def connect(provider: Provider, body: ConnectIn, p: Principal = Depends(current_principal)):
    try:
        return sync.connect(p.user_id, provider, body.username.strip())
    except sync.SyncRefused as e:
        _refused(e)


@router.delete("/integrations/{provider}", status_code=204, tags=["Integrations"])
def disconnect(
    provider: Provider, delete_data: bool = Query(False), p: Principal = Depends(current_principal)
):
    """Stops syncing. `delete_data=true` also erases imported observations for this provider; past assessment
    snapshots keep the values they were built from (they are immutable)."""
    try:
        sync.disconnect(p.user_id, provider, delete_data)
    except sync.SyncRefused as e:
        _refused(e)


@router.post(
    "/integrations/{provider}/sync",
    status_code=202,
    tags=["Sync"],
    dependencies=[Depends(expensive)],
)
def start_sync(
    provider: Provider,
    tasks: BackgroundTasks,
    response: Response,
    p: Principal = Depends(current_principal),
):
    """Starts a sync and returns at once with a run id; poll GET /sync-runs/{id} until status != 'running'.

    Retry semantics: a repeat while a run is in flight is 409 and within the cooldown 429 + Retry-After, so a
    retried POST can never start a second concurrent run. A run orphaned by a crash is marked failed/abandoned.
    """
    try:
        run_id, job = sync.start_sync(p.user_id, provider)
    except sync.SyncRefused as e:
        _refused(e)
    tasks.add_task(sync.execute_run, *job)
    response.headers["Location"] = f"/api/v1/sync-runs/{run_id}"
    return {"id": run_id, "provider": provider, "status": "running"}


@router.get("/sync-runs", tags=["Sync"])
def list_sync_runs(
    provider: Provider,
    limit: int = Query(10, ge=1, le=50),
    p: Principal = Depends(current_principal),
):
    return {"items": sync.list_runs(p.user_id, provider, limit)}


@router.get("/sync-runs/{run_id}", tags=["Sync"])
def get_sync_run(run_id: str, p: Principal = Depends(current_principal)):
    try:
        return sync.get_run(p.user_id, run_id)
    except IndexError:
        raise HTTPException(status_code=404, detail="Sync run not found") from None


@router.get("/me/data-quality", tags=["Data quality"])
def data_quality(p: Principal = Depends(current_principal)):
    """Per connected provider: last run outcome plus how many records were quarantined, by rule code."""
    return {
        "items": fetch_all(
            """
            SELECT c.provider, c.external_username, c.status AS connection_status, c.last_success_at,
                   (SELECT row_to_json(x) FROM (SELECT r.id::text AS id, r.status, r.completed_at, r.safe_error_code,
                           r.records_created, r.records_rejected FROM sync_runs r WHERE r.connection_id = c.id
                           ORDER BY r.started_at DESC LIMIT 1) x) AS last_run,
                   COALESCE((SELECT json_object_agg(rule_code, n) FROM (SELECT d.rule_code, count(*) AS n
                           FROM data_quality_results d JOIN sync_runs r ON r.id = d.sync_run_id
                           WHERE r.connection_id = c.id AND d.outcome = 'rejected' GROUP BY d.rule_code) q), '{}'::json)
                           AS rejected_by_rule
            FROM integration_connections c WHERE c.user_id = %s AND c.status <> 'disconnected' ORDER BY c.provider
        """,
            (p.user_id,),
        )
    }


# ── Assessments ────────────────────────────────────────────────────────
def _build_evidence(cur, profile_id: str, cgpa) -> dict:
    """Latest run's observations per provider, with provenance and the run id they came from."""
    ev = {
        "evidence_version": EVIDENCE_VERSION,
        "cgpa": None if cgpa is None else {"value": float(cgpa), "provenance": "user_entered"},
    }
    for provider in ("github", "leetcode"):
        cur.execute(
            """
            SELECT o.observation_type, o.value_num::float, o.provenance::text, o.sync_run_id::text, r.completed_at,
                   o.source_object_id
            FROM source_observations o JOIN sync_runs r ON r.id = o.sync_run_id
            WHERE o.profile_id = %s AND o.provider = %s AND o.sync_run_id = (
                SELECT sync_run_id FROM source_observations WHERE profile_id = %s AND provider = %s
                ORDER BY collected_at DESC LIMIT 1)
        """,
            (profile_id, provider, profile_id, provider),
        )
        rows = cur.fetchall()
        if not rows:
            ev[provider] = None
            continue
        values: dict[str, Any] = {}
        days: dict[date, int] = {}
        for typ, num, _, _, _, obj_id in rows:
            if (
                typ == "github_contribution_day"
            ):  # calendar days feed the trend rule, not the flat values
                days[date.fromisoformat(obj_id)] = int(num or 0)
            elif (
                typ == "github_repo_commit_count"
            ):  # per-repo rows: report the sum and how many repos fed it
                values["commits_in_sampled_repos"] = values.get("commits_in_sampled_repos", 0) + (
                    num or 0
                )
                values["repos_sampled"] = values.get("repos_sampled", 0) + 1
            else:
                values[typ] = num
        ev[provider] = block = {
            "sync_run_id": rows[0][3],
            "synced_at": rows[0][4].isoformat(),
            "provenance": rows[0][2],
            "values": values,
        }
        if (
            days
        ):  # deterministic rule, no model: active weeks last 4 vs previous 8 (features/as_of.py)
            f = features_as_of(days, max(days))
            trend = activity_trend(f["weekly_counts"])
            direction = trend.pop("direction")
            values.update(trend)
            block["activity_trend"] = {
                "direction": direction,
                "rule": "active weeks, last 4 vs previous 8",
                "as_of": f["as_of"],
                "features_version": FEATURES_VERSION,
                "provenance": rows[0][2],
            }
    return ev


_ASSESSMENT = (
    "id::text AS id, assessment_type, readiness_score::float AS readiness_score, category, reason, "
    "model_version, created_at"
)


@router.post(
    "/assessments", status_code=201, tags=["Assessments"], dependencies=[Depends(expensive)]
)
def create_assessment(p: Principal = Depends(current_principal)):
    """Snapshot the caller's current evidence. Real accounts get an evidence summary and a non-score result
    (`insufficient_evidence`) until a validated real-user feature pipeline exists; no number is invented."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id::text, cgpa FROM profiles WHERE user_id = %s", (p.user_id,))
        prof = cur.fetchone()
        if not prof:
            raise HTTPException(status_code=409, detail="Create a profile first.")
        ev = _build_evidence(cur, prof[0], prof[1])
        reason = (
            NO_SCORE_REASON
            if (ev["github"] or ev["leetcode"])
            else "No synced provider data yet. Connect an account and run a sync."
        )
        cur.execute(
            f"INSERT INTO assessments (profile_id, assessment_type, reason, evidence) "
            f"VALUES (%s, 'insufficient_evidence', %s, %s::jsonb) RETURNING {_ASSESSMENT}",
            (prof[0], reason, json.dumps(ev)),
        )
        return _dicts(cur)[0]


@router.get("/assessments", tags=["Assessments"])
def list_assessments(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100_000),
    p: Principal = Depends(current_principal),
):
    items = fetch_all(
        f"SELECT {_ASSESSMENT} FROM assessments WHERE profile_id IN ({_MY_PROFILE}) "
        "ORDER BY created_at DESC, id LIMIT %s OFFSET %s",
        (p.user_id, limit, offset),
    )
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/assessments/{assessment_id}", tags=["Assessments"])
def get_assessment(assessment_id: str, p: Principal = Depends(current_principal)):
    return _one(
        fetch_all(
            f"SELECT {_ASSESSMENT} FROM assessments WHERE id::text = %s AND profile_id IN ({_MY_PROFILE})",
            (assessment_id, p.user_id),
        ),
        "Assessment",
    )


@router.get("/assessments/{assessment_id}/evidence", tags=["Assessments"])
def get_assessment_evidence(assessment_id: str, p: Principal = Depends(current_principal)):
    return _one(
        fetch_all(
            "SELECT id::text AS assessment_id, evidence FROM assessments "
            f"WHERE id::text = %s AND profile_id IN ({_MY_PROFILE})",
            (assessment_id, p.user_id),
        ),
        "Assessment",
    )


# ── Privacy: export, deletion, consent ─────────────────────────────────
@router.get("/me/export", tags=["Privacy"], dependencies=[Depends(expensive)])
def export_my_data(p: Principal = Depends(current_principal)):
    """All stored data for the caller as JSON (format `pis-export-v1`). Contains no secrets: none are stored."""
    return privacy.export_data(p.user_id)


@router.post("/me/data-requests/deletion", tags=["Privacy"])
def request_deletion(confirm: bool = Query(False), p: Principal = Depends(current_principal)):
    """Irreversibly erases profile, connections, observations and assessments, and locks the account (later
    requests with old or new tokens get 403). `confirm=true` is required."""
    if not confirm:
        raise HTTPException(
            status_code=400, detail="Pass confirm=true to permanently delete your data."
        )
    return privacy.delete_account(p.user_id)


@router.get("/me/data-requests", tags=["Privacy"])
def list_data_requests(p: Principal = Depends(current_principal)):
    return {
        "items": fetch_all(
            "SELECT id::text AS id, kind, status, requested_at, updated_at FROM data_requests "
            "WHERE user_id = %s ORDER BY requested_at DESC LIMIT 50",
            (p.user_id,),
        )
    }


class ConsentIn(BaseModel):
    research: bool


@router.get("/me/privacy", tags=["Privacy"])
def get_privacy(p: Principal = Depends(current_principal)):
    """Optional consent state. Core processing (profile, synced provider data, assessments) needs no consent."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT research_consent_at FROM users WHERE id = %s", (p.user_id,))
        at = cur.fetchone()[0]
    return {"research_consent": at is not None, "research_consent_at": at}


@router.put("/me/privacy", tags=["Privacy"])
def put_privacy(body: ConsentIn, p: Principal = Depends(current_principal)):
    """Grant or revoke optional research/training use. Recorded only: no such use exists yet."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET research_consent_at = CASE WHEN %s THEN COALESCE(research_consent_at, now()) END "
            "WHERE id = %s RETURNING research_consent_at",
            (body.research, p.user_id),
        )
        at = cur.fetchone()[0]
        privacy.audit(
            cur,
            "consent.research_granted" if body.research else "consent.research_revoked",
            p.user_id,
        )
    return {"research_consent": at is not None, "research_consent_at": at}
