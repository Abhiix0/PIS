"""Phase 15: readiness probe and structured logs (DB-free)."""
import json
import logging
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.logger import JsonFormatter
from app.main import app

client = TestClient(app)




def test_ready_ok():
    with patch("app.main.get_connection") as gc, patch("app.main.pending", return_value=[]), \
         patch("app.main.active_version", return_value="v1"):
        gc.return_value.__enter__.return_value = object()
        r = client.get("/health/ready")
    assert r.status_code == 200 and r.json() == {"status": "ready"}


def test_ready_503_on_pending_migrations_and_no_model():
    with patch("app.main.get_connection") as gc, patch("app.main.pending", return_value=["009.sql"]), \
         patch("app.main.active_version", side_effect=RuntimeError("none")):
        gc.return_value.__enter__.return_value = object()
        r = client.get("/health/ready")
    assert r.status_code == 503 and r.json()["problems"] == ["migrations", "model"]


def test_ready_503_when_db_down():
    with patch("app.main.get_connection", side_effect=RuntimeError("down")), \
         patch("app.main.active_version", return_value="v1"):
        r = client.get("/health/ready")
    assert r.status_code == 503 and r.json()["problems"] == ["database"]


def test_json_log_carries_request_id():
    rec = logging.LogRecord("pis", logging.INFO, __file__, 1, "hello", None, None)
    rec.request_id = "abc123"
    out = json.loads(JsonFormatter().format(rec))
    assert out["request_id"] == "abc123" and out["msg"] == "hello" and out["level"] == "INFO"
