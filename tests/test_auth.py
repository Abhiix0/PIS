"""Authn/authz guards. DB-free except the owner-isolation block, which needs a DB migrated through 004."""
import uuid
import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

import config
from app import auth
from app.main import app
from tests.conftest import _OTHER, bearer, make_token

client = TestClient(app)
OPS = {"roles": ["pis_operator"]}

# every operator-only route family; the guard runs before any handler/DB access
OPERATOR_ROUTES = [
    ("get", "/students"), ("get", "/students/1"), ("post", "/students"), ("patch", "/students/1"),
    ("get", "/students/1/status"), ("get", "/students/1/history"),
    ("post", "/ingest/coding/1"), ("post", "/ingest/github/1"), ("post", "/ingest/coding/real/1"), ("post", "/ingest/github/real/1"),
    ("post", "/predict/1"), ("get", "/prediction/1"), ("get", "/insights/1"), ("get", "/ranking"), ("get", "/features/1"),
    ("post", "/pipeline/1"), ("post", "/pipeline/batch"), ("post", "/admin/retrain"), ("get", "/admin/retrain/status"),
]
USER_ROUTES = [("get", "/me"), ("post", "/auth/logout"), ("post", "/profiles"), ("get", "/profiles/x"), ("patch", "/profiles/x")]


@pytest.fixture
def fake_user(monkeypatch):
    """Replace the users-table lookup so no DB is needed."""
    state = {"status": "active", "valid_after": None}
    monkeypatch.setattr(auth, "_load_user", lambda sub, email: {"id": f"uid-{sub}", **state})
    return state


def call(method, path, **kw):
    return getattr(client, method)(path, **kw)


@pytest.mark.parametrize("method,path", OPERATOR_ROUTES + USER_ROUTES)
def test_anonymous_rejected(method, path):
    assert call(method, path).status_code == 401


@pytest.mark.parametrize("method,path", OPERATOR_ROUTES)
def test_regular_user_cannot_use_operator_routes(fake_user, method, path):
    assert call(method, path, headers=bearer(make_token("alice"))).status_code == 403


def test_operator_passes_guard(fake_user, monkeypatch):
    from app.routers import students
    monkeypatch.setattr(students, "get_connection", lambda: (_ for _ in ()).throw(RuntimeError("db")))
    c = TestClient(app, raise_server_exceptions=False)
    # 500 (handler reached, fake DB down), not 401/403
    assert c.get("/students", headers=bearer(make_token("ops", **OPS))).status_code == 500


def test_admin_key_header_no_longer_grants_anything(fake_user):
    assert client.post("/admin/retrain", headers={"X-Admin-Key": "k" * 32}).status_code == 401


def test_client_supplied_role_headers_are_ignored(fake_user):
    r = client.get("/students", headers={**bearer(make_token("alice")), "X-Role": "pis_operator", "X-Admin": "1"})
    assert r.status_code == 403


@pytest.mark.parametrize("token", [
    make_token("a", exp_in=-10),          # expired
    make_token("a", key=_OTHER),          # wrong signing key
    make_token("a", aud="someone-else"),  # wrong audience
    "not.a.jwt",
])
def test_bad_tokens_rejected(fake_user, token):
    assert client.get("/me", headers=bearer(token)).status_code == 401


def test_unsigned_alg_none_rejected(fake_user):
    t = jwt.encode({"sub": "a", "aud": "pis-api", "iss": "https://idp.test/", "exp": 9999999999, "iat": 1}, None, algorithm="none")
    assert client.get("/me", headers=bearer(t)).status_code == 401


def test_revoked_session_rejected_but_new_token_works(fake_user, monkeypatch):
    from app.routers import profiles
    monkeypatch.setattr(profiles, "get_connection", lambda: (_ for _ in ()).throw(RuntimeError("db")))
    c = TestClient(app, raise_server_exceptions=False)
    fake_user["valid_after"] = datetime.now(timezone.utc) - timedelta(seconds=30)
    assert c.get("/me", headers=bearer(make_token("alice", iat_offset=-60))).status_code == 401
    assert c.get("/me", headers=bearer(make_token("alice"))).status_code == 500  # auth passed


def test_suspended_account_rejected(fake_user):
    fake_user["status"] = "suspended"
    assert client.get("/me", headers=bearer(make_token("alice"))).status_code == 403


def test_auth_unconfigured_fails_closed(fake_user, monkeypatch):
    monkeypatch.setattr(config, "AUTH_JWKS_URL", "")
    assert client.get("/me", headers=bearer(make_token("alice"))).status_code == 401


def test_repeated_bad_credentials_are_throttled(fake_user):
    codes = [client.get("/me", headers=bearer("junk")).status_code for _ in range(25)]
    assert codes[0] == 401 and codes[-1] == 429


def test_expensive_operations_rate_limited(fake_user, monkeypatch):
    from app.routers import pipeline
    monkeypatch.setattr(pipeline, "get_connection", lambda: (_ for _ in ()).throw(RuntimeError("db")))
    c = TestClient(app, raise_server_exceptions=False)
    h = bearer(make_token("ops", **OPS))
    codes = [c.post("/pipeline/1", headers=h).status_code for _ in range(12)]
    assert codes[0] == 500 and codes[-1] == 429


def test_oversized_body_rejected(fake_user):
    h = {**bearer(make_token("alice")), "Content-Type": "application/json"}
    assert client.post("/profiles", content=b"x" * 70_000, headers=h).status_code == 413


def test_batch_size_bounded(fake_user):
    r = client.post("/pipeline/batch", json={"student_ids": list(range(1, 30))}, headers=bearer(make_token("ops", **OPS)))
    assert r.status_code == 422


# ── Owner isolation: needs a DB migrated through 004 ─────────────────
def _db_ready():
    try:
        from ingest.db_connection import get_connection
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.profiles')")
            return cur.fetchone()[0] is not None
    except Exception:
        return False


db = pytest.mark.skipif(not _db_ready(), reason="needs migrated DB (python -m ingest.migrate)")


@db
def test_profile_owner_isolation():
    a = bearer(make_token(f"a-{uuid.uuid4().hex}"))
    b = bearer(make_token(f"b-{uuid.uuid4().hex}"))
    r = client.post("/profiles", json={"display_name": "A", "cgpa": 8}, headers=a)
    assert r.status_code == 201
    pid = r.json()["id"]
    assert client.post("/profiles", json={"display_name": "A2"}, headers=a).status_code == 409
    assert client.get(f"/profiles/{pid}", headers=a).json()["display_name"] == "A"
    assert client.get("/me", headers=a).json()["profile_id"] == pid
    # B by id: indistinguishable from nonexistent, for read and write
    assert client.get(f"/profiles/{pid}", headers=b).status_code == 404
    assert client.patch(f"/profiles/{pid}", json={"display_name": "pwned"}, headers=b).status_code == 404
    assert client.get(f"/profiles/{uuid.uuid4()}", headers=b).status_code == 404
    assert client.patch(f"/profiles/{pid}", json={"cgpa": 9}, headers=a).json()["cgpa"] == 9
    assert client.get(f"/profiles/{pid}", headers=a).json()["display_name"] == "A"


@db
def test_logout_revokes_existing_tokens():
    sub = f"c-{uuid.uuid4().hex}"
    old = bearer(make_token(sub, iat_offset=-5))
    assert client.get("/me", headers=old).status_code == 200
    assert client.post("/auth/logout", headers=old).status_code == 204
    assert client.get("/me", headers=old).status_code == 401
    time.sleep(1.5)  # iat has 1s resolution
    assert client.get("/me", headers=bearer(make_token(sub))).status_code == 200
