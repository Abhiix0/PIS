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


PROTECTED = [
    ("get", "/me"),
    ("put", "/me/profile"),
    ("get", "/integrations"),
    ("put", "/integrations/github"),
    ("delete", "/integrations/github"),
    ("post", "/integrations/github/sync"),
    ("get", "/sync-runs?provider=github"),
    ("get", f"/sync-runs/{uuid.uuid4()}"),
    ("get", "/me/data-quality"),
    ("post", "/assessments"),
    ("get", "/assessments"),
    ("get", f"/assessments/{uuid.uuid4()}"),
    ("get", f"/assessments/{uuid.uuid4()}/evidence"),
    ("get", f"/assessments/{uuid.uuid4()}/compare/{uuid.uuid4()}"),
    ("post", "/me/data-requests/deletion"),
    ("get", "/me/data-requests"),
    ("get", "/me/export"),
    ("get", "/me/privacy"),
    ("put", "/me/privacy"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_every_v1_route_requires_a_token(method, path):
    error_of(getattr(client, method)(V1 + path), 401, "unauthenticated")


def test_every_v1_route_is_in_the_protected_list():
    routes = {
        (m, r.path) for r in app.routes if r.path.startswith(V1) for m in r.methods - {"HEAD"}
    }
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


def test_unknown_and_unversioned_paths_use_the_same_envelope():
    error_of(client.get("/me"), 404, "not_found")  # legacy path is gone
    error_of(client.get("/students"), 404, "not_found")


def test_oversize_body_is_enveloped():
    error_of(
        client.put(V1 + "/me/profile", content=b"x" * (config.MAX_BODY_BYTES + 1), headers=U().h),
        413,
        "payload_too_large",
    )


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


def test_disconnect_hides_the_connection_and_is_owner_scoped(user):
    other = U()
    error_of(other.delete("/integrations/github"), 404, "not_found")
    assert user.delete("/integrations/github").status_code == 204
    assert user.get("/integrations").json()["items"] == []
    error_of(user.delete("/integrations/github"), 404, "not_found")
    error_of(user.post("/integrations/github/sync"), 404, "not_found")


def test_data_quality_summarises_quarantine(user):
    obs = gh(("a", 1))
    obs[1] = __import__("dataclasses").replace(
        obs[1], value_num=-5
    )  # fails validation: quarantined, not stored
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
    assert (
        a["assessment_type"] == "rules_assessment"
        and a["readiness_score"] is None
        and a["model_version"] is None
    )
    assert (
        a["result"]["assessment_version"] == "rules-v1"
        and "score':" not in str(a["result"]).lower()
    )
    d = {x["dimension"]: x for x in a["result"]["dimensions"]}
    assert d["D2"]["evidence_state"] == "sufficient" and d["D1"]["evidence_state"] == "no_evidence"
    assert d["D4"]["values"][0]["provenance"] == "user_entered"
    ev = user.get(f"/assessments/{a['id']}/evidence").json()["evidence"]
    assert ev["cgpa"] == {"value": 8.1, "provenance": "user_entered"}
    assert (
        ev["github"]["provenance"] == "observed"
        and ev["github"]["values"]["commits_in_sampled_repos"] == 7
    )
    assert ev["github"]["sync_run_id"] and ev["leetcode"] is None
    assert user.get(f"/assessments/{a['id']}").json()["id"] == a["id"]


def test_assessment_without_data_says_so_and_needs_a_profile():
    error_of(U().post("/assessments"), 409, "conflict")
    u = U()
    u.put("/me/profile", json={"display_name": "T"})
    a = u.post("/assessments").json()
    assert (
        "No synced provider data" in a["reason"] and a["assessment_type"] == "insufficient_evidence"
    )
    assert {x["evidence_state"] for x in a["result"]["dimensions"] if x["dimension"] != "D4"} == {
        "no_evidence"
    }


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
    assert (
        other.get("/me/data-quality").json()["items"] == []
        and other.get("/integrations").json()["items"] == []
    )


def test_assessment_rows_are_immutable(user):
    import psycopg2

    from ingest.db_connection import get_connection

    aid = user.post("/assessments").json()["id"]
    with pytest.raises(psycopg2.Error):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE assessments SET reason = 'x' WHERE id::text = %s", (aid,))


def _count(sql, *args):
    from ingest.db_connection import get_connection

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchone()[0]


def test_disconnect_can_delete_imported_data_but_keeps_assessments(user):
    with with_adapter(gh(("a", 3))):
        assert user.post("/integrations/github/sync").status_code == 202
    aid = user.post("/assessments").json()["id"]
    uid = user.get("/me").json()["profile"]["id"]
    q = "SELECT count(*) FROM source_observations WHERE profile_id::text = %s"
    assert _count(q, uid) > 0
    assert user.delete("/integrations/github?delete_data=true").status_code == 204
    assert _count(q, uid) == 0
    assert (
        user.get(f"/assessments/{aid}/evidence").json()["evidence"]["github"] is not None
    )  # immutable snapshot


def test_export_has_own_data_only_and_no_secrets(user):
    with with_adapter(gh(("a", 3))):
        user.post("/integrations/github/sync")
    user.post("/assessments")
    other = U()
    other.put("/me/profile", json={"display_name": "Other"})
    r = user.get("/me/export")
    d = r.json()
    assert (
        r.status_code == 200
        and d["format"] == "pis-export-v1"
        and d["profile"]["display_name"] == "T"
    )
    assert (
        d["observations"]
        and d["assessments"]
        and d["integrations"][0]["external_username"] == "octo"
    )
    assert "Other" not in r.text and not any(
        w in r.text.lower() for w in ("token", "secret", "password")
    )


def test_deletion_requires_confirm_erases_and_locks_account(user):
    error_of(user.post("/me/data-requests/deletion"), 400, "bad_request")
    user.post("/assessments")
    pid = user.get("/me").json()["profile"]["id"]
    r = user.post("/me/data-requests/deletion?confirm=true")
    assert r.status_code == 200 and r.json()["status"] == "completed"
    assert user.get("/me").status_code == 403 and user.get("/me/export").status_code == 403
    assert _count("SELECT count(*) FROM profiles WHERE id::text = %s", pid) == 0
    assert _count("SELECT count(*) FROM assessments WHERE profile_id::text = %s", pid) == 0
    assert _count("SELECT count(*) FROM audit_events WHERE action = 'account.deleted'") >= 1


def test_consent_is_off_by_default_and_revocable():
    u = U()
    assert u.get("/me/privacy").json()["research_consent"] is False
    assert u.put("/me/privacy", json={"research": True}).json()["research_consent"] is True
    assert u.put("/me/privacy", json={"research": False}).json()["research_consent"] is False


# ── Phase 11: what the desktop session flow depends on ────────────────
def test_profile_is_visible_only_to_its_owner():
    a, b = U(), U()
    a.put("/me/profile", json={"display_name": "Ada", "cgpa": 9})
    assert b.get("/me").json()["profile"] is None  # same endpoint, different token: nothing of A's
    b.put("/me/profile", json={"display_name": "Bob"})
    assert a.get("/me").json()["profile"]["display_name"] == "Ada"


def test_expired_and_revoked_tokens_are_401_with_the_envelope():
    sub = f"v1-{uuid.uuid4()}"
    expired = client.get(f"{V1}/me", headers=bearer(make_token(sub, exp_in=-10)))
    assert expired.status_code == 401
    live = bearer(make_token(sub, iat_offset=-5))
    assert client.get(f"{V1}/me", headers=live).status_code == 200
    assert client.post("/auth/logout", headers=live).status_code == 204
    assert (
        client.get(f"{V1}/me", headers=live).status_code == 401
    )  # logout revokes tokens issued before it


# ── Phase 3.1: evidence contract (evidence-v2) ────────────────────────
def _evidence(u):
    aid = u.post("/assessments").json()["id"]
    return u.get(f"/assessments/{aid}/evidence").json()["evidence"]


def _leetcode_user(monkeypatch, parts):
    from unittest.mock import patch

    from ingest.provider import Observation

    monkeypatch.setattr(config, "LEETCODE_INTEGRATION_ENABLED", True)
    u = U()
    u.put("/me/profile", json={"display_name": "L"})
    assert u.put("/integrations/leetcode", json={"username": "someone"}).status_code == 200
    obs = [Observation("leetcode", f"leetcode_solved_{d}", n) for d, n in parts]
    with patch("ingest.leetcode_api.fetch_leetcode_observations", return_value=(obs, False)):
        assert u.post("/integrations/leetcode/sync").status_code == 202
    return u


def test_evidence_v2_derives_leetcode_total_only_from_all_three(monkeypatch):
    ev = _evidence(_leetcode_user(monkeypatch, (("easy", 5), ("medium", 0), ("hard", 1))))
    lc = ev["leetcode"]
    assert ev["evidence_version"] == "evidence-v2" and lc["values"]["leetcode_solved_all"] == 6
    assert lc["derived"] == ["leetcode_solved_all"] and lc["value_states"]["leetcode_solved_medium"]
    ev = _evidence(_leetcode_user(monkeypatch, (("easy", 5), ("hard", 1))))  # missing is not zero
    assert "leetcode_solved_all" not in ev["leetcode"]["values"] and ev["leetcode"]["derived"] == []


class _Cur:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, *a):
        pass

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return None


def test_block_provenance_is_the_weakest_and_independent_of_row_order():
    from datetime import UTC, datetime

    from app.routers.v1 import _build_evidence

    t = datetime(2024, 1, 1, tzinfo=UTC)
    a = ("leetcode_solved_easy", 1.0, "observed", "r1", t, None, "present", "unknown", t)
    b = ("leetcode_solved_hard", 0.0, "inferred", "r1", t, None, "measured_zero", "unknown", t)
    for rows in ([a, b], [b, a]):
        blk = _build_evidence(_Cur(rows), "p", None)["leetcode"]
        assert blk["provenance"] == "inferred" and blk["value_states"]["leetcode_solved_hard"] == (
            "measured_zero"
        )


def test_missing_calendar_day_is_not_counted_as_zero():
    from datetime import UTC, datetime

    from app.routers.v1 import _build_evidence

    t = datetime(2024, 1, 1, tzinfo=UTC)
    rows = [
        (
            "github_contribution_day",
            None,
            "observed",
            "r1",
            t,
            "2024-01-01",
            "not_collected",
            "day",
            t,
        )
    ]
    blk = _build_evidence(_Cur(rows), "p", None)["github"]
    assert "activity_trend" not in blk and blk["values"] == {}


def test_same_data_gives_identical_evidence(user):
    with with_adapter(gh(("a", 3), ("b", 4))):
        user.post("/integrations/github/sync")
    first, second = _evidence(user), _evidence(user)
    assert first == second


def test_profile_validation_bounds(user):
    for bad in (
        {"graduation_year": 1999},
        {"graduation_year": 2101},
        {"cgpa": -0.1},
        {"cgpa": 10.1},
    ):
        error_of(
            user.put("/me/profile", json={"display_name": "T", **bad}), 422, "validation_error"
        )
    ok = user.put("/me/profile", json={"display_name": "T", "cgpa": 10, "graduation_year": 2026})
    assert ok.status_code == 200


def test_first_login_creates_the_user_row_once():
    u = U()
    sub = "first-" + uuid.uuid4().hex
    h = bearer(make_token(sub))
    q = "SELECT count(*) FROM users WHERE auth_subject = %s"
    assert _count(q, sub) == 0
    for _ in range(2):
        assert client.get(f"{V1}/me", headers=h).status_code == 200
    assert _count(q, sub) == 1 and u.get("/me").json()["profile"] is None


def test_every_route_with_an_id_hides_other_users_records(user):
    with with_adapter(gh(("a", 1))):
        rid = user.post("/integrations/github/sync").json()["id"]
    aid = user.post("/assessments").json()["id"]
    ids = {"{assessment_id}": aid, "{other_id}": aid, "{run_id}": rid}
    other = U()
    other.put("/me/profile", json={"display_name": "O"})
    seen = 0
    for r in app.routes:
        if not r.path.startswith(V1) or not any(k in r.path for k in ids):
            continue
        path = r.path[len(V1) :]
        for k, v in ids.items():
            path = path.replace(k, v)
        for m in r.methods - {"HEAD"}:
            error_of(getattr(other, m.lower())(path), 404, "not_found")
            seen += 1
    assert seen >= 3  # assessment, evidence, sync run


def test_compare_two_own_snapshots_and_hide_them_from_others(user):
    first = user.post("/assessments").json()["id"]
    with with_adapter(gh(("a", 3))):
        user.post("/integrations/github/sync")
    second = user.post("/assessments").json()
    assert second["result"]["recommendations"] is not None
    c = user.get(f"/assessments/{first}/compare/{second['id']}").json()
    assert c["comparable"] is True and c["from"]["id"] == first and c["to"]["id"] == second["id"]
    assert any("state changed" in n for n in c["disclosures"])
    other = U()
    other.put("/me/profile", json={"display_name": "O"})
    error_of(other.get(f"/assessments/{first}/compare/{second['id']}"), 404, "not_found")
    error_of(user.get(f"/assessments/{first}/compare/{uuid.uuid4()}"), 404, "not_found")
