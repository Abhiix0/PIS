"""Authn/authz guards. DB-free except the owner-isolation block, which needs a DB migrated through 004."""

import time
import uuid
from datetime import UTC, datetime, timedelta

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
    ("post", "/admin/retrain"),
    ("get", "/admin/retrain/status"),
    ("get", "/admin/models"),
    ("post", "/admin/models/v1/approve"),
    ("post", "/admin/models/v1/activate"),
    ("post", "/admin/models/rollback"),
    ("get", "/admin/audit-events"),
    ("get", "/admin/sync-failures"),
]
ME = "/api/v1/me"
USER_ROUTES = [("get", ME), ("post", "/auth/logout")]


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
    import ingest.db_connection as dbc

    monkeypatch.setattr(dbc, "get_connection", lambda: (_ for _ in ()).throw(RuntimeError("db")))
    c = TestClient(app, raise_server_exceptions=False)
    # 500 (handler reached, fake DB down), not 401/403; same envelope as every other error
    r = c.get("/admin/audit-events", headers=bearer(make_token("ops", **OPS)))
    assert r.status_code == 500 and r.json()["error"]["code"] == "internal_error"
    assert "RuntimeError" not in r.text


def test_admin_key_header_no_longer_grants_anything(fake_user):
    assert client.post("/admin/retrain", headers={"X-Admin-Key": "k" * 32}).status_code == 401


def test_client_supplied_role_headers_are_ignored(fake_user):
    r = client.get(
        "/admin/audit-events",
        headers={**bearer(make_token("alice")), "X-Role": "pis_operator", "X-Admin": "1"},
    )
    assert r.status_code == 403


@pytest.mark.parametrize(
    "token",
    [
        make_token("a", exp_in=-10),  # expired
        make_token("a", key=_OTHER),  # wrong signing key
        make_token("a", aud="someone-else"),  # wrong audience
        "not.a.jwt",
    ],
)
def test_bad_tokens_rejected(fake_user, token):
    assert client.get(ME, headers=bearer(token)).status_code == 401


def test_unsigned_alg_none_rejected(fake_user):
    t = jwt.encode(
        {"sub": "a", "aud": "pis-api", "iss": "https://idp.test/", "exp": 9999999999, "iat": 1},
        None,
        algorithm="none",
    )
    assert client.get(ME, headers=bearer(t)).status_code == 401


def test_revoked_session_rejected_but_new_token_works(fake_user, monkeypatch):
    from app.routers import v1

    monkeypatch.setattr(v1, "fetch_all", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db")))
    c = TestClient(app, raise_server_exceptions=False)
    fake_user["valid_after"] = datetime.now(UTC) - timedelta(seconds=30)
    assert c.get(ME, headers=bearer(make_token("alice", iat_offset=-60))).status_code == 401
    assert c.get(ME, headers=bearer(make_token("alice"))).status_code == 500  # auth passed


def test_suspended_account_rejected(fake_user):
    fake_user["status"] = "suspended"
    assert client.get(ME, headers=bearer(make_token("alice"))).status_code == 403


def test_auth_unconfigured_fails_closed(fake_user, monkeypatch):
    monkeypatch.setattr(config, "AUTH_JWKS_URL", "")
    assert client.get(ME, headers=bearer(make_token("alice"))).status_code == 401


def test_repeated_bad_credentials_are_throttled(fake_user):
    codes = [client.get(ME, headers=bearer("junk")).status_code for _ in range(25)]
    assert codes[0] == 401 and codes[-1] == 429


def test_expensive_operations_rate_limited(fake_user, monkeypatch):
    import app.routers.admin as admin

    monkeypatch.setattr(admin, "_run_retrain", lambda: admin._retrain_lock.release())
    h = bearer(make_token("ops", **OPS))
    monkeypatch.setattr(admin, "_audit", lambda *a, **k: None)
    codes = [client.post("/admin/retrain", headers=h).status_code for _ in range(12)]
    assert codes[-1] == 429 and 202 in codes


def test_oversized_body_rejected(fake_user):
    h = {**bearer(make_token("alice")), "Content-Type": "application/json"}
    assert client.put("/api/v1/me/profile", content=b"x" * 70_000, headers=h).status_code == 413


# ── Owner isolation: needs a DB migrated through 004 ─────────────────
def _db_ready():
    try:
        from ingest.db_connection import get_connection

        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.profiles')")
            return cur.fetchone()[0] is not None
    except Exception:
        return False


@pytest.fixture
def _need_db():
    if not _db_ready():  # checked per test so the session DB fixture (conftest) is already in place
        pytest.skip("needs migrated DB (python -m ingest.migrate)")


db = pytest.mark.usefixtures("_need_db")


@db
def test_logout_revokes_existing_tokens():
    sub = f"c-{uuid.uuid4().hex}"
    old = bearer(make_token(sub, iat_offset=-5))
    assert client.get(ME, headers=old).status_code == 200
    assert client.post("/auth/logout", headers=old).status_code == 204
    assert client.get(ME, headers=old).status_code == 401
    time.sleep(1.5)  # iat has 1s resolution
    assert client.get(ME, headers=bearer(make_token(sub))).status_code == 200
