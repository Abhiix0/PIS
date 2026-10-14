import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# ── Student endpoints ─────────────────────────────────────────────────

def test_health_check():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_get_existing_student():
    r = client.get("/students/1")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == 1
    assert "name"  in data
    assert "cgpa"  in data
    assert "email" in data

def test_get_nonexistent_student_returns_404():
    r = client.get("/students/99999")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()

def test_create_student_normalises_branch():
    unique_email = f"pytest_{uuid.uuid4().hex[:8]}@pis.dev"
    payload = {
        "name":   "Test Student",
        "email":  unique_email,
        "cgpa":   7.5,
        "branch": "cse"   # lowercase → should normalise to "CSE"
    }
    r = client.post("/students", json=payload)
    assert r.status_code == 201
    assert r.json()["branch"] == "CSE"

def test_create_student_invalid_cgpa_returns_422():
    payload = {"name":"X", "email":"x@x.com", "cgpa":15.0, "branch":"CSE"}
    r = client.post("/students", json=payload)
    assert r.status_code == 422  # Pydantic validation catches cgpa > 10

# ── Feature + prediction endpoints ───────────────────────────────────

def test_get_features_existing_student():
    r = client.get("/features/1")
    assert r.status_code == 200
    data = r.json()
    assert data["student_id"] == 1
    assert data["total_problems"] > 0

def test_get_prediction_existing():
    r = client.get("/prediction/1")
    assert r.status_code == 200
    data = r.json()
    assert 0 <= data["readiness_score"] <= 100
    assert data["category"] in ["Ready", "Near Ready", "Needs Improvement"]

def test_get_prediction_missing_returns_404():
    r = client.get("/prediction/99999")
    assert r.status_code == 404

# ── Insights endpoint ─────────────────────────────────────────────────

@pytest.fixture
def strong_student():
    """A self-contained strong profile (recent, many hard problems, heavy commits); removed afterwards.
    Seed students are not strong (student 1 has 18 problems dated 2024), so tests must not assume so."""
    from ingest.db_connection import get_connection
    from features.compute import run_feature_sql_for_student
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO students (name, email, cgpa, branch) "
                        "VALUES ('Strong Fixture', %s, 9.0, 'CSE') RETURNING id",
                        (f"strong-{uuid.uuid4().hex[:8]}@test.dev",))
            sid = cur.fetchone()[0]
            cur.execute("INSERT INTO coding_activity (student_id, problem_id, difficulty, solved_at) "
                        "SELECT %s, 'F' || g, 'hard', CURRENT_DATE - (g %% 60) FROM generate_series(1, 80) g", (sid,))
            cur.execute("INSERT INTO github_activity (student_id, repo_name, commits, commit_date) "
                        "SELECT %s, 'repo' || g, 40, CURRENT_DATE - (g * 3) FROM generate_series(1, 20) g", (sid,))
    run_feature_sql_for_student(sid)
    yield sid
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM students WHERE id = %s", (sid,))


def test_insights_strong_student_has_no_weaknesses(strong_student):
    r = client.get(f"/insights/{strong_student}")
    assert r.status_code == 200
    data = r.json()
    assert data["weaknesses"] == []

def test_insights_weak_student_has_recommendations():
    r = client.get("/insights/8")
    assert r.status_code == 200
    data = r.json()
    assert len(data["weaknesses"]) > 0
    assert len(data["recommendations"]) > 0
    assert data["recommendations"][0]["priority"] == 1
    assert data["recommendations"][0]["tier"] == "critical"

def test_ranking_returns_ordered_results():
    r = client.get("/ranking?limit=8")
    assert r.status_code == 200
    data = r.json()
    ranks = [item["global_rank"] for item in data]
    assert ranks == sorted(ranks)

def test_ranking_branch_filter():
    r = client.get("/ranking?branch=CSE&limit=10")
    assert r.status_code == 200
    data = r.json()
    assert all(item["branch"] == "CSE" for item in data)