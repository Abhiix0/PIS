"""Phase 15: readiness probe and structured logs (DB-free)."""

import json
import logging
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.logger import JsonFormatter
from app.main import app
from tests.conftest import bearer, make_token

client = TestClient(app)


def test_ready_ok():
    with (
        patch("app.main.get_connection") as gc,
        patch("app.main.pending", return_value=[]),
        patch("app.main.active_version", return_value="v1"),
    ):
        gc.return_value.__enter__.return_value = object()
        r = client.get("/health/ready")
    assert r.status_code == 200 and r.json() == {"status": "ready"}


def test_ready_503_on_pending_migrations_and_no_model():
    with (
        patch("app.main.get_connection") as gc,
        patch("app.main.pending", return_value=["009.sql"]),
        patch("app.main.active_version", side_effect=RuntimeError("none")),
    ):
        gc.return_value.__enter__.return_value = object()
        r = client.get("/health/ready")
    assert r.status_code == 503 and r.json()["problems"] == ["migrations", "model"]


def test_ready_503_when_db_down():
    with (
        patch("app.main.get_connection", side_effect=RuntimeError("down")),
        patch("app.main.active_version", return_value="v1"),
    ):
        r = client.get("/health/ready")
    assert r.status_code == 503 and r.json()["problems"] == ["database"]


def test_json_log_carries_request_id():
    rec = logging.LogRecord("pis", logging.INFO, __file__, 1, "hello", None, None)
    rec.request_id = "abc123"
    out = json.loads(JsonFormatter().format(rec))
    assert out["request_id"] == "abc123" and out["msg"] == "hello" and out["level"] == "INFO"


def _staging(monkeypatch):
    monkeypatch.setattr("config.APP_ENV", "staging")


def test_staging_ready_without_model(monkeypatch):
    _staging(monkeypatch)
    with (
        patch("app.main.get_connection") as gc,
        patch("app.main.pending", return_value=[]),
        patch("app.main.active_version", side_effect=RuntimeError("none")),
    ):
        gc.return_value.__enter__.return_value = object()
        r = client.get("/health/ready")
    assert r.status_code == 200 and r.json() == {"status": "ready"}


def test_staging_ready_still_needs_db_and_migrations(monkeypatch):
    _staging(monkeypatch)
    with (
        patch("app.main.get_connection") as gc,
        patch("app.main.pending", return_value=["009.sql"]),
    ):
        gc.return_value.__enter__.return_value = object()
        r = client.get("/health/ready")
    assert r.status_code == 503 and r.json()["problems"] == ["migrations"]


def test_staging_detailed_reports_model_none(monkeypatch):
    _staging(monkeypatch)
    with (
        patch("app.main.check_db_connection", return_value=True),
        patch("app.main.get_connection", side_effect=RuntimeError("x")),
        patch("app.main.active_version", side_effect=RuntimeError("none")),
    ):
        body = client.get("/health/detailed").json()
    assert body["model_version"] == "none" and body["status"] == "ok"


def _lifespan(monkeypatch, env, load_active):
    monkeypatch.setattr("config.APP_ENV", env)
    monkeypatch.setattr("config.DATABASE_URL", "postgresql://u:s3cr3t-real@h/db")
    monkeypatch.setattr("config.AUTH_ISSUER", "https://idp.example/")
    monkeypatch.setattr("config.AUTH_AUDIENCE", "pis")
    monkeypatch.setattr("config.AUTH_JWKS_URL", "https://idp.example/jwks")
    with (
        patch("app.main.check_db_connection", return_value=True),
        patch("app.main.get_connection"),
        patch("app.main.pending", return_value=[]),
        patch("app.main.load_active", side_effect=load_active),
        patch("app.main.close_pool"),
    ):
        with TestClient(app):
            pass


def test_staging_starts_without_model(monkeypatch):
    _lifespan(monkeypatch, "staging", RuntimeError("no bundle"))


def test_local_start_fails_without_model(monkeypatch):
    import pytest

    with pytest.raises(RuntimeError, match="Startup failed"):
        _lifespan(monkeypatch, "local", RuntimeError("no bundle"))


def test_cors_allowed_origin_and_preflight(monkeypatch):
    origin = "http://tauri.localhost"
    from starlette.middleware.cors import CORSMiddleware

    cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
    monkeypatch.setitem(cors.kwargs, "allow_origins", [origin])
    app.middleware_stack = None  # rebuild with the patched allowlist
    try:
        pre = client.options(
            "/api/v1/me",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert pre.status_code == 200
        assert pre.headers["access-control-allow-origin"] == origin
        assert "authorization" in pre.headers["access-control-allow-headers"].lower()
        other = client.options(
            "/api/v1/me",
            headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"},
        )
        assert "access-control-allow-origin" not in other.headers
        r = client.get("/api/v1/me", headers={"Origin": origin})
        assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"
        assert r.headers["access-control-allow-origin"] == origin
    finally:
        app.middleware_stack = None


def test_cors_default_denies_every_origin():
    r = client.get("/health", headers={"Origin": "http://tauri.localhost"})
    assert "access-control-allow-origin" not in r.headers


def test_logs_carry_the_request_id_and_never_the_bearer_token(caplog):
    token = make_token("log-check", aud="wrong-audience")  # rejected before any DB access
    with caplog.at_level(logging.INFO, logger="pis"):
        r = client.get("/api/v1/me", headers={**bearer(token), "X-Request-ID": "rid-log-1"})
    assert r.headers["x-request-id"] == "rid-log-1"
    text = " ".join(
        f"{rec.getMessage()} {rec.__dict__.get('request_id')}" for rec in caplog.records
    )
    assert "rid-log-1" in text and token not in text and "Bearer" not in text


def test_unhandled_error_is_logged_with_its_request_id_and_not_returned(caplog):
    quiet = TestClient(app, raise_server_exceptions=False)
    with (
        caplog.at_level(logging.ERROR, logger="pis"),
        patch("app.main.check_db_connection", side_effect=RuntimeError("secret-internal")),
    ):
        r = quiet.get("/health/detailed", headers={"X-Request-ID": "rid-err-1"})
    assert r.status_code == 500 and "secret-internal" not in r.text
    assert r.json()["error"]["request_id"] == "rid-err-1"
    assert any("rid-err-1" in rec.getMessage() for rec in caplog.records)
