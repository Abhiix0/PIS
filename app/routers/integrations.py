from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import Principal, current_principal, expensive
from services import sync

router = APIRouter(prefix="/integrations", tags=["Integrations"])
Provider = Literal["github", "leetcode"]


class ConnectIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)  # public username only; no tokens are accepted


def _refused(e: sync.SyncRefused):
    headers = {"Retry-After": str(e.retry_after)} if e.retry_after else None
    raise HTTPException(status_code=e.status, detail=e.detail, headers=headers)


@router.get("")
def list_connections(p: Principal = Depends(current_principal)):
    return sync.list_connections(p.user_id)


@router.put("/{provider}")
def connect(provider: Provider, body: ConnectIn, p: Principal = Depends(current_principal)):
    try:
        return sync.connect(p.user_id, provider, body.username.strip())
    except sync.SyncRefused as e:
        _refused(e)


@router.post("/{provider}/sync", dependencies=[Depends(expensive)])
def run_sync(provider: Provider, p: Principal = Depends(current_principal)):
    """Returns the finished run. A failed run is a 200 with status 'failed' and a safe error code."""
    try:
        return sync.run_sync(p.user_id, provider)
    except sync.SyncRefused as e:
        _refused(e)


@router.get("/{provider}/sync-runs")
def sync_runs(provider: Provider, limit: int = Query(10, ge=1, le=50), p: Principal = Depends(current_principal)):
    return sync.list_runs(p.user_id, provider, limit)
