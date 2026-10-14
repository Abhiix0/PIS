"""Contract tests for /api/v1. Need a DB migrated through 007; providers are mocked."""
import uuid

import pytest
from fastapi.testclient import TestClient

import config
from app.main import app
from tests.conftest import bearer, make_token
from tests.test_sync import gh, with_adapter

client = TestClient(app)
V1 = "/api/v1"


class U:
    def __init__(self):
        self.h = bearer(make_token(f"v1-{uuid.uuid4()}"))

    def __getattr__(self, m):
        return lambda path, **kw: getattr(client, m)(V1 + path, headers=self.h, **kw)


@pytest.fixture(autouse=True)
def _no_cooldown(monkeypatch):
    monkeypatch.setattr(config, "SYNC_COOLDOWN_SECONDS", 0)


@pytest.fixture
def user():
    u = U()
    assert u.put("/me/profile", json={"display_name": "T", "cgpa": 8.1}).status_code == 201
    assert u.put("/integrations/github", json={"username": "octo"}).status_code == 200
    return u


def error_of(r, status, code):
    assert r.status_code == status, r.text
    e = r.json()["error"]
    assert e["code"] == code and e["message"] and "request_id" in e
    assert "detail" not in r.json()


PROTECTED = [("get", "/me"), ("put", "/me/profile"), ("get", "/integrations"), ("put", "/integrations/github"),
             ("post", "/integrations/github/sync"), ("get", "/sync-runs?provider=github"), ("get", f"/sync-runs/{uuid.uuid4()}"),
             ("get", "/me/data-quality"), ("post", "/assessments"), ("get", "/assessments"),
             ("get", f"/assessments/{uuid.uuid4()}"), ("get", f"/assessments/{uuid.uuid4()}/evidence"),
             ("post", "/me/data-requests/export"), ("get", "/me/data-requests")]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_every_v1_route_requires_a_token(method, path):
    error_of(getattr(client, method)(V1 + path), 401, "unauthenticated")


def test_every_v1_route_is_in_the_protected_list():
    routes = {(m, r.path) for r in app.routes if r.path.startswith(V1) for m in r.methods - {"HEAD"}}
    assert len(routes) == len(PROTECTED)  # a new route must be added to PROTECTED


def test_openapi_documents_v1():
    spec = client.get("/openapi.json").json()
    paths = [p for p in spec["paths"] if p.startswith(V1)]
    assert f"{V1}/assessments/{{assessment_id}}/evidence" in paths and len(paths) >= 12
    assert "202" in spec["paths"][f"{V1}/integrations/{{provider}}/sync"]["post"]["responses"]


def test_profile_put_is_idempotent_and_timestamps_are_utc():
    u = U()
    assert u.get("/me").json()["profile"] is None
    r = u.put("/me/profile", json={"display_name": "A"})
    assert r.status_code == 201 and r.json()["created_at"].endswith("+00:00")
    r = u.put("/me/profile", json={"display_name": "B", "cgpa": 7})
    assert r.status_code == 200 and u.get("/me").json()["profile"]["display_name"] == "B"


def test_validation_error_envelope_does_not_echo_input():
    r = U().put("/me/profile", json={"display_name": "x", "cgpa": 99})
    error_of(r, 422, "validation_error")
    assert "99" not in str(r.json()["error"]["message"])


def test_legacy_routes_keep_detail_shape():
    assert client.get("/me").json() == {"detail": "Not authenticated"}


def test_oversize_body_is_enveloped():
    error_of(client.put(V1 + "/me/profile", content=b"x" * (config.MAX_BODY_BYTES + 1), headers=U().h), 413, "payload_too_large")


def test_sync_is_accepted_then_pollable_to_completion(user):
    with with_adapter(gh(("a", 3), ("b", 4))):
        r = user.post("/integrations/github/sync")
        assert r.status_code == 202  # TestClient runs background tasks before returning
        assert r.headers["location"] == f"{V1}/sync-runs/{r.json()['id']}"
        run = user.get(f"/sync-runs/{r.json()['id']}").json()
    assert run["status"] == "succeeded" and run["records_created"] == 3
    assert user.get("/sync-runs?provider=github").json()["items"][0]["id"] == run["id"]


def test_failed_sync_run_is_explicit_and_safe(user):
    from ingest.provider import ProviderError
    with with_adapter(ProviderError("rate_limited", "secret-internal-detail")):
        rid = user.post("/integrations/github/sync").json()["id"]
    run = user.get(f"/sync-runs/{rid}").json()
    assert run["status"] == "failed" and run["safe_error_code"] == "rate_limited"
    assert "secret-internal-detail" not in str(run)


def test_sync_refusals_are_enveloped(user, monkeypatch):
    error_of(U().post("/integrations/github/sync"), 404, "not_found")
    monkeypatch.setattr(config, "SYNC_COOLDOWN_SECONDS", 600)
    with with_adapter(gh(("a", 1))):
        user.post("/integrations/github/sync")
    r = user.post("/integrations/github/sync")
    error_of(r, 429, "rate_limited")
    assert int(r.headers["retry-after"]) > 0
    error_of(user.get(f"/sync-runs/{uuid.uuid4()}"), 404, "not_found")


def test_data_quality_summarises_quarantine(user):
    obs = gh(("a", 1))
    obs[1] = __import__("dataclasses").replace(obs[1], value_num=-5)  # fails validation: quarantined, not stored
    with with_adapter(obs):
        user.post("/integrations/github/sync")
    item = user.get("/me/data-quality").json()["items"][0]
    assert item["provider"] == "github" and item["last_run"]["status"] == "partial"
    assert sum(item["rejected_by_rule"].values()) == 1


def test_assessment_is_a_non_score_evidence_snapshot(user):
    with with_adapter(gh(("a", 3), ("b", 4))):
        user.post("/integrations/github/sync")
    r = user.post("/assessments")
    assert r.status_code == 201
    a = r.json()
    assert a["assessment_type"] == "insufficient_evidence" and a["readiness_score"] is None and a["model_version"] is None
    ev = user.get(f"/assessments/{a['id']}/evidence").json()["evidence"]
    assert ev["cgpa"] == {"value": 8.1, "provenance": "user_entered"}
    assert ev["github"]["provenance"] == "observed" and ev["github"]["values"]["commits_in_sampled_repos"] == 7
    assert ev["github"]["sync_run_id"] and ev["leetcode"] is None
    assert user.get(f"/assessments/{a['id']}").json()["id"] == a["id"]


def test_assessment_without_data_says_so_and_needs_a_profile():
    error_of(U().post("/assessments"), 409, "conflict")
    u = U()
    u.put("/me/profile", json={"display_name": "T"})
    assert "No synced provider data" in u.post("/assessments").json()["reason"]


def test_assessment_history_is_paginated_newest_first(user):
    ids = [user.post("/assessments").json()["id"] for _ in range(3)]
    page = user.get("/assessments?limit=2").json()
    assert [i["id"] for i in page["items"]] == ids[::-1][:2] and page["limit"] == 2
    assert [i["id"] for i in user.get("/assessments?limit=2&offset=2").json()["items"]] == [ids[0]]
    error_of(user.get("/assessments?limit=1000"), 422, "validation_error")


def test_assessments_and_runs_are_owner_isolated(user):
    with with_adapter(gh(("a", 1))):
        rid = user.post("/integrations/github/sync").json()["id"]
    aid = user.post("/assessments").json()["id"]
    other = U()
    other.put("/me/profile", json={"display_name": "O"})
    assert other.get("/assessments").json()["items"] == []
    error_of(other.get(f"/assessments/{aid}"), 404, "not_found")
    error_of(other.get(f"/assessments/{aid}/evidence"), 404, "not_found")
    error_of(other.get(f"/sync-runs/{rid}"), 404, "not_found")
    assert other.get("/me/data-quality").json()["items"] == [] and other.get("/integrations").json()["items"] == []


def test_assessment_rows_are_immutable(user):
    import psycopg2
    from ingest.db_connection import get_connection
    aid = user.post("/assessments").json()["id"]
    with pytest.raises(psycopg2.Error):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE assessments SET reason = 'x' WHERE id::text = %s", (aid,))


def test_data_requests_are_idempotent_and_owner_scoped():
    u = U()
    first = u.post("/me/data-requests/deletion")
    assert first.status_code == 202 and first.json()["status"] == "requested"
    assert u.post("/me/data-requests/deletion").json()["id"] == first.json()["id"]
    assert [r["kind"] for r in u.get("/me/data-requests").json()["items"]] == ["deletion"]
    assert U().get("/me/data-requests").json()["items"] == []
    error_of(u.post("/me/data-requests/bogus"), 422, "validation_error")
