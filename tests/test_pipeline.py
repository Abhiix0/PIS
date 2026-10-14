import pytest
from fastapi.testclient import TestClient
from app.main import app

from tests.conftest import make_token

# Legacy /students, /pipeline, ... routes are operator-only since Phase 5.
client = TestClient(app, headers={"Authorization": "Bearer " + make_token("ops", roles=["pis_operator"])})


def test_pipeline_nonexistent_student_returns_404():
    r = client.post("/pipeline/99999")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_list_students_returns_array():
    r = client.get("/students")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 8  # at least the 8 seed students
    for item in data:
        assert "id" in item
        assert "name" in item
        assert "has_prediction" in item


def test_student_status_fields_present():
    r = client.get("/students/1/status")
    assert r.status_code == 200
    data = r.json()
    assert "pipeline_stage" in data
    assert data["pipeline_stage"] in ["no_data", "features_computed", "predicted", "complete"]
    assert "features_computed" in data
    assert "prediction_exists" in data


def test_student_status_nonexistent_returns_404():
    r = client.get("/students/99999/status")
    assert r.status_code == 404


def test_batch_pipeline_rejects_empty_list():
    r = client.post("/pipeline/batch", json={"student_ids": []})
    assert r.status_code == 422  # Pydantic min_length validation


def test_batch_pipeline_rejects_oversized_list():
    r = client.post("/pipeline/batch", json={"student_ids": list(range(1, 25))})  # 24 > max 20
    assert r.status_code == 422


def test_health_detailed_returns_components():
    r = client.get("/health/detailed")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "database" in data
    assert "models" in data
    assert "student_count" in data
    assert data["student_count"] >= 8
