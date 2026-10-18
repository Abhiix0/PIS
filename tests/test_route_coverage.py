"""Phase 14 regression: every registered route rejects anonymous callers except the health allowlist (DB-free)."""

import re

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app

PUBLIC = {
    "/health",
    "/health/detailed",
    "/health/ready",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}
ROUTES = [
    (m, r.path)
    for r in app.routes
    if isinstance(r, APIRoute)
    for m in r.methods
    if r.path not in PUBLIC
]
client = TestClient(app)


@pytest.mark.parametrize("method,path", ROUTES)
def test_route_requires_token(method, path):
    resp = client.request(method, re.sub(r"\{[^}]+\}", "1", path))
    assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"


def test_oversized_body_rejected():
    resp = client.post("/students", content=b"x", headers={"content-length": "999999999"})
    assert resp.status_code == 413
