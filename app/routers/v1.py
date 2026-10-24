"""Stable client contract, mounted at /api/v1. Every query is scoped by the token's user_id in the SQL itself.

Errors use the envelope {"error": {"code", "message", "request_id"}} (see app/main.py). Timestamps are ISO 8601
with a +00:00 offset (the DB pool pins the session time zone to UTC).
"""

import json
from datetime import UTC, date, datetime
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

import config
from app.auth import Principal, current_principal, expensive
from features.as_of import FEATURES_VERSION, activity_trend, features_as_of
from ingest.db_connection import fetch_all, get_connection
from services import assessment as rules
from services import privacy, sync

router = APIRouter(prefix="/api/v1")
session_router = APIRouter(tags=["Session"])  # unprefixed: the desktop client calls /auth/logout
Provider = Literal["github", "leetcode"]
EVIDENCE_VERSION = "evidence-v2"
# Strongest to weakest; a block shows the weakest provenance among its rows (docs/data/data-dictionary.md).
_PROVENANCE_ORDER = ("observed", "user_entered", "derived", "inferred", "synthetic")
_LEETCODE_PARTS = ("leetcode_solved_easy", "leetcode_solved_medium", "leetcode_solved_hard")
RULES_REASON = (
    "Per-dimension evidence states from fixed rules (rules-v1). There is no score: provider data cannot "
    "support one without inventing values."
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
def _meta(precision, collected) -> dict:
    return {"event_at_precision": precision, "collected_at": collected.isoformat()}


def _build_evidence(cur, profile_id: str, cgpa) -> dict:
    """Latest run's observations per provider, with provenance and the run id they came from."""
    ev: dict[str, Any] = {
        "evidence_version": EVIDENCE_VERSION,
        "cgpa": None if cgpa is None else {"value": float(cgpa), "provenance": "user_entered"},
        "runs": {},
    }
    for provider in ("github", "leetcode"):
        cur.execute(
            """
            SELECT c.status, r.id::text, r.status, r.safe_error_code, r.completed_at
            FROM integration_connections c LEFT JOIN LATERAL (
                SELECT id, status, safe_error_code, completed_at FROM sync_runs
                WHERE connection_id = c.id AND status <> 'running' ORDER BY started_at DESC LIMIT 1) r ON true
            WHERE c.user_id = (SELECT user_id FROM profiles WHERE id = %s) AND c.provider = %s
              AND c.status <> 'disconnected'
        """,
            (profile_id, provider),
        )
        conn_row = cur.fetchone()
        ev["runs"][provider] = conn_row and {
            "connection_status": conn_row[0],
            "last_run": conn_row[1]
            and {
                "id": conn_row[1],
                "status": conn_row[2],
                "safe_error_code": conn_row[3],
                "completed_at": conn_row[4] and conn_row[4].isoformat(),
            },
        }
        cur.execute(
            """
            SELECT o.observation_type, o.value_num::float, o.provenance::text, o.sync_run_id::text, r.completed_at,
                   o.source_object_id, o.value_state::text, o.event_at_precision, o.collected_at
            FROM source_observations o JOIN sync_runs r ON r.id = o.sync_run_id
            WHERE o.profile_id = %s AND o.provider = %s AND o.sync_run_id = (
                SELECT sync_run_id FROM source_observations WHERE profile_id = %s AND provider = %s
                ORDER BY collected_at DESC LIMIT 1)
            ORDER BY o.observation_type, o.source_object_id NULLS FIRST
        """,
            (profile_id, provider, profile_id, provider),
        )
        rows = cur.fetchall()
        if not rows:
            ev[provider] = None
            continue
        values: dict[str, Any] = {}
        states: dict[str, str] = {}
        meta: dict[str, dict] = {}
        days: dict[date, int] = {}
        for typ, num, _, _, _, obj_id, state, precision, collected in rows:
            if (
                typ == "github_contribution_day"
            ):  # calendar days feed the trend rule, not the flat values
                if num is not None:  # a missing day is unknown, never 0
                    days[date.fromisoformat(obj_id)] = int(num)
                    meta.setdefault("activity_days", _meta(precision, collected))
            elif (
                typ == "github_repo_commit_count"
            ):  # per-repo rows: report the sum and how many repos fed it
                if num is not None:
                    values["commits_in_sampled_repos"] = values.get(
                        "commits_in_sampled_repos", 0
                    ) + (num)
                    values["repos_sampled"] = values.get("repos_sampled", 0) + 1
                    meta.setdefault("commits_in_sampled_repos", _meta(precision, collected))
                    meta.setdefault("repos_sampled", _meta(precision, collected))
                    # measured_zero only if every sampled repo reported 0
                    prev = states.get("commits_in_sampled_repos", "measured_zero")
                    states["commits_in_sampled_repos"] = (
                        "measured_zero" if prev == state == "measured_zero" else "present"
                    )
            else:
                values[typ] = num
                states[typ] = state
                meta[typ] = _meta(precision, collected)
        provenance = max((r[2] for r in rows), key=_PROVENANCE_ORDER.index)
        derived = []
        if all(values.get(k) is not None for k in _LEETCODE_PARTS):
            values["leetcode_solved_all"] = sum(values[k] for k in _LEETCODE_PARTS)
            states["leetcode_solved_all"] = (
                "present" if values["leetcode_solved_all"] else "measured_zero"
            )
            derived.append(
                "leetcode_solved_all"
            )  # a sum of the three present counts; missing is never 0
        ev[provider] = block = {
            "sync_run_id": rows[0][3],
            "synced_at": rows[0][4].isoformat(),
            "provenance": provenance,
            "values": values,
            "value_states": states,
            "value_meta": meta,
            "derived": derived,
        }
        if "leetcode_solved_all" in derived:
            meta["leetcode_solved_all"] = meta["leetcode_solved_easy"]
        if (
            days
        ):  # deterministic rule, no model: active weeks last 4 vs previous 8 (features/as_of.py)
            f = features_as_of(days, max(days))
            trend = activity_trend(f["weekly_counts"])
            direction = trend.pop("direction")
            values.update(trend)
            meta.update({k: meta["activity_days"] for k in trend})
            block["activity_trend"] = {
                "direction": direction,
                "rule": "active weeks, last 4 vs previous 8",
                "as_of": f["as_of"],
                "features_version": FEATURES_VERSION,
                "provenance": provenance,
            }
    return ev


_ASSESSMENT = (
    "id::text AS id, assessment_type, readiness_score::float AS readiness_score, category, reason, "
    "model_version, result, created_at"
)


@router.post(
    "/assessments", status_code=201, tags=["Assessments"], dependencies=[Depends(expensive)]
)
def create_assessment(p: Principal = Depends(current_principal)):
    """Snapshot the caller's current evidence and the deterministic rules-v1 result computed from it. There is no
    score: with provider evidence the type is `rules_assessment`, otherwise `insufficient_evidence`."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id::text, cgpa FROM profiles WHERE user_id = %s", (p.user_id,))
        prof = cur.fetchone()
        if not prof:
            raise HTTPException(status_code=409, detail="Create a profile first.")
        ev = _build_evidence(cur, prof[0], prof[1])
        result = rules.compute_assessment(
            ev, datetime.now(UTC), config.LEETCODE_INTEGRATION_ENABLED
        )
        if rules.has_provider_evidence(result):
            kind, reason = rules.RESULT_TYPE, RULES_REASON
        else:
            kind, reason = (
                "insufficient_evidence",
                "No synced provider data yet. Connect an account and run a sync.",
            )
        cur.execute(
            f"INSERT INTO assessments (profile_id, assessment_type, reason, evidence, result) "
            f"VALUES (%s, %s, %s, %s::jsonb, %s::jsonb) RETURNING {_ASSESSMENT}",
            (prof[0], kind, reason, json.dumps(ev), json.dumps(result)),
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
