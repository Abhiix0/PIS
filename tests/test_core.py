"""
Core tests for PIS — run without a live DB or model files.
    pytest tests/test_core.py -v
"""

from unittest.mock import patch

# ── Test 2: Health endpoint returns expected shape ────────────────────


def test_health_endpoint():
    # Patch lifespan startup checks so TestClient doesn't need DB or models
    with (
        patch("app.main.check_db_connection", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
    ):
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"
    assert "version" in data


# ── Test 3: Label category boundaries are correct ────────────────────


def test_score_to_category_boundaries():
    from ml.labels import score_to_category

    assert score_to_category(65.0) == "Ready"
    assert score_to_category(64.9) == "Near Ready"
    assert score_to_category(40.0) == "Near Ready"
    assert score_to_category(39.9) == "Needs Improvement"
    assert score_to_category(0.0) == "Needs Improvement"
    assert score_to_category(100.0) == "Ready"
