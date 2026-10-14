"""Legacy `students` routes (operator, demo data): a failed source must not add synthetic rows or clear data."""
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from ingest.db_connection import get_connection
from ingest.provider import ProviderError
from tests.conftest import make_token

client = TestClient(app, headers={"Authorization": "Bearer " + make_token("ops", roles=["pis_operator"])})


@pytest.fixture
def student():
    body = {"name": "Legacy Test", "email": f"{uuid.uuid4().hex[:10]}@example.com", "cgpa": 7.5, "branch": "CSE",
            "github_username": "octo", "leetcode_username": "someone"}
    r = client.post("/students", json=body)
    assert r.status_code in (200, 201), r.text
    sid = r.json()["id"]
    yield sid
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM students WHERE id = %s", (sid,))


def count(table, sid):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {table} WHERE student_id = %s", (sid,))
        return cur.fetchone()[0]


def test_real_leetcode_route_no_longer_fabricates_rows(student):
    assert client.post(f"/ingest/coding/real/{student}").status_code == 501
    assert count("coding_activity", student) == 0


@pytest.mark.parametrize("code,status", [("rate_limited", 503), ("unavailable", 503), ("not_found", 422)])
def test_github_failure_returns_error_and_writes_nothing(student, code, status):
    with patch("app.routers.ingest.fetch_github_data", side_effect=ProviderError(code)):
        r = client.post(f"/ingest/github/real/{student}")
    assert r.status_code == status and count("github_activity", student) == 0


def test_github_success_rows_are_marked_observed(student):
    from datetime import date
    rows = [{"repo_name": "a", "commits": 4, "commit_date": date(2024, 3, 1)}]
    with patch("app.routers.ingest.fetch_github_data", return_value=rows):
        assert client.post(f"/ingest/github/real/{student}").status_code == 200
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT provenance::text FROM github_activity WHERE student_id = %s", (student,))
        assert cur.fetchall() == [("observed",)]


def test_pipeline_with_failing_sources_adds_no_synthetic_data_and_reports_the_failure(student):
    with patch("ingest.github_api.fetch_github_data", side_effect=ProviderError("rate_limited")):
        r = client.post(f"/pipeline/{student}?force_refresh=true")
    assert r.status_code == 200, r.text
    steps = {s["step"]: s for s in r.json()["pipeline_steps"]}
    assert steps["github_ingestion"]["status"] == "error" and steps["github_ingestion"]["error"] == "rate_limited"
    assert steps["coding_ingestion"]["status"] == "skipped"
    assert count("github_activity", student) == 0 and count("coding_activity", student) == 0


def test_seed_and_generated_rows_default_to_synthetic():
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT DISTINCT provenance::text FROM coding_activity WHERE student_id <= 8")
        assert {r[0] for r in cur.fetchall()} <= {"synthetic"}
