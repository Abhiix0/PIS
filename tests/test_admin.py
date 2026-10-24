"""Operator routes (/admin/*): audit trail, error mapping, retrain lock. Bundle operations are mocked; needs the test DB."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import admin
from ml import bundle
from tests.conftest import bearer, make_token

client = TestClient(app)
SUB = f"ops-{uuid.uuid4()}"
OPS = bearer(make_token(SUB, roles=["pis_operator"]))


def _events():
    return client.get("/admin/audit-events", headers=OPS).json()


def test_model_actions_are_audited_with_the_operator_subject(monkeypatch):
    monkeypatch.setattr(bundle, "approve", lambda v, who, note: None)
    monkeypatch.setattr(bundle, "activate", lambda v, who: None)
    monkeypatch.setattr(bundle, "rollback", lambda who: "v0")
    assert (
        client.post("/admin/models/vX/approve?note=ok", headers=OPS).json()["status"] == "approved"
    )
    assert client.post("/admin/models/vX/activate", headers=OPS).json()["status"] == "active"
    assert client.post("/admin/models/rollback", headers=OPS).json()["version"] == "v0"
    mine = [e for e in _events() if e["actor_subject"] == SUB]
    assert {"model.approved", "model.activated", "model.rolled_back"} <= {e["action"] for e in mine}


def test_bundle_errors_become_409_envelopes(monkeypatch):
    def boom(*a):
        raise bundle.BundleError("not approved")

    monkeypatch.setattr(bundle, "activate", boom)
    r = client.post("/admin/models/vX/activate", headers=OPS)
    assert r.status_code == 409 and r.json()["error"]["code"] == "conflict"


def test_list_models_and_sync_failures_are_readable_by_operators():
    assert isinstance(client.get("/admin/models", headers=OPS).json(), list)
    rows = client.get("/admin/sync-failures?limit=5", headers=OPS).json()
    assert isinstance(rows, list) and all("username" not in str(r).lower() for r in rows)


@pytest.fixture
def lock_free():
    admin._retrain_lock.acquire(blocking=False)
    admin._retrain_lock.release()
    yield
    if admin._retrain_lock.locked():
        admin._retrain_lock.release()


def test_retrain_runs_once_at_a_time(monkeypatch, lock_free):
    monkeypatch.setattr(admin, "_run_retrain", lambda: None)  # leaves the lock held
    first = client.post("/admin/retrain", headers=OPS)
    assert first.status_code == 202
    assert client.post("/admin/retrain", headers=OPS).status_code == 409
    assert client.get("/admin/retrain/status", headers=OPS).json()["state"] == "running"


def test_failed_retrain_reports_only_the_exception_type(monkeypatch, lock_free):
    def boom():
        raise ValueError("secret detail")

    monkeypatch.setattr("features.compute.run_feature_sql", boom)
    admin._retrain_lock.acquire()
    admin._run_retrain()
    st = client.get("/admin/retrain/status", headers=OPS).json()
    assert st["state"] == "failed" and st["error"] == "ValueError" and "secret" not in str(st)
    assert not admin._retrain_lock.locked()
