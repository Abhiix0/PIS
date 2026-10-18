"""Sync lifecycle + integrations API. Needs a DB migrated through 005 (python -m ingest.migrate); providers are mocked."""

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import psycopg2
import pytest
from fastapi.testclient import TestClient

import config
from app.main import app
from ingest.db_connection import get_connection
from ingest.provider import Observation, ProviderError
from tests.conftest import bearer, make_token

client = TestClient(app)
V1 = "/api/v1"
PUSHED = datetime(2024, 3, 1, 12, tzinfo=UTC)


def gh(*repos, count=None):
    """Adapter result: repo count + one commit-count observation per (name, commits)."""
    obs = [
        Observation("github", "github_public_repo_count", len(repos) if count is None else count)
    ]
    obs += [
        Observation(
            "github",
            "github_repo_commit_count",
            n,
            source_object_id=r,
            event_at=PUSHED,
            event_at_precision="repo_push",
        )
        for r, n in repos
    ]
    return obs


class User:
    def __init__(self):
        self.h = bearer(make_token(f"sync-{uuid.uuid4()}"))

    def call(self, method, path, **kw):
        return getattr(client, method)(path, headers=self.h, **kw)

    def sync(self, provider="github"):
        """v1 starts a run (202); TestClient has run the background task by then, so return the finished run."""
        r = self.call("post", f"{V1}/integrations/{provider}/sync")
        if r.status_code != 202:
            return r
        return self.call("get", r.headers["Location"])

    def runs(self):
        return self.call("get", f"{V1}/sync-runs?provider=github").json()["items"]


@pytest.fixture(autouse=True)
def _no_cooldown(monkeypatch):
    monkeypatch.setattr(config, "SYNC_COOLDOWN_SECONDS", 0)


@pytest.fixture
def user():
    u = User()
    assert u.call("put", f"{V1}/me/profile", json={"display_name": "T"}).status_code == 201
    assert u.call("put", f"{V1}/integrations/github", json={"username": "octo"}).status_code == 200
    return u


def with_adapter(result):
    effect = result if isinstance(result, Exception) else None
    return patch(
        "ingest.github_api.fetch_github_observations",
        side_effect=effect,
        return_value=None if effect else (result, False),
    )


def observations_of(user_obj):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT o.observation_type, o.source_object_id, o.value_num, o.provenance::text, o.value_state::text, "
            "o.sync_run_id IS NOT NULL FROM source_observations o JOIN profiles p ON p.id = o.profile_id "
            "JOIN users u ON u.id = p.user_id WHERE u.auth_subject = %s ORDER BY 1, 2",
            (user_obj_sub(user_obj),),
        )
        return cur.fetchall()


def user_obj_sub(u):
    import jwt

    return jwt.decode(u.h["Authorization"][7:], options={"verify_signature": False})["sub"]


def test_success_stores_observed_aggregates_traceable_to_a_run(user):
    with with_adapter(gh(("a", 12), ("b", 0))):
        run = user.sync().json()
    assert run["status"] == "succeeded" and (
        run["records_observed"],
        run["records_created"],
        run["records_rejected"],
    ) == (3, 3, 0)
    rows = observations_of(user)
    assert all(r[3] == "observed" and r[5] for r in rows)
    assert {(r[1], r[2], r[4]) for r in rows if r[1]} == {
        ("a", 12, "present"),
        ("b", 0, "measured_zero"),
    }
    assert user.runs()[0]["id"] == run["id"]


def test_empty_profile_is_success_with_measured_zero(user):
    with with_adapter(gh()):
        run = user.sync().json()
    assert run["status"] == "succeeded"
    rows = observations_of(user)
    assert rows == [("github_public_repo_count", None, 0, "observed", "measured_zero", True)]


@pytest.mark.parametrize(
    "err,code",
    [
        (ProviderError("rate_limited", retry_after=30), "rate_limited"),
        (ProviderError("unavailable"), "unavailable"),
        (ProviderError("malformed"), "malformed"),
        (ProviderError("not_found"), "not_found"),
    ],
)
def test_failed_sync_keeps_last_known_good_and_writes_nothing(user, err, code):
    with with_adapter(gh(("a", 5))):
        assert user.sync().json()["status"] == "succeeded"
    before = observations_of(user)
    with with_adapter(err):
        run = user.sync().json()
    assert run["status"] == "failed" and run["safe_error_code"] == code
    assert observations_of(user) == before
    conn = user.call("get", f"{V1}/integrations").json()["items"][0]
    assert conn["status"] == "error" and conn["last_success_at"] is not None
    with with_adapter(gh(("a", 6))):  # recovery resets the connection
        assert user.sync().json()["status"] == "succeeded"
    assert user.call("get", f"{V1}/integrations").json()["items"][0]["status"] == "connected"


def test_partial_provider_result_is_marked_partial(user):
    with patch("ingest.github_api.fetch_github_observations", return_value=(gh(("a", 1)), True)):
        run = user.sync().json()
    assert run["status"] == "partial" and run["safe_error_code"] == "partial_result"


def test_invalid_records_are_quarantined_with_a_reason_not_stored_as_zero(user):
    bad = [
        Observation(
            "github",
            "github_repo_commit_count",
            -3,
            source_object_id="neg",
            event_at=PUSHED,
            event_at_precision="repo_push",
        ),
        Observation(
            "github",
            "github_repo_commit_count",
            4,
            source_object_id="future",
            event_at=datetime(2999, 1, 1, tzinfo=UTC),
            event_at_precision="repo_push",
        ),
        Observation(
            "github",
            "github_repo_commit_count",
            2,
            source_object_id="dup",
            event_at=PUSHED,
            event_at_precision="repo_push",
        ),
        Observation(
            "github",
            "github_repo_commit_count",
            2,
            source_object_id="dup",
            event_at=PUSHED,
            event_at_precision="repo_push",
        ),
    ]
    with with_adapter(gh() + bad):
        run = user.sync().json()
    assert run["status"] == "partial" and (run["records_created"], run["records_rejected"]) == (
        2,
        3,
    )
    assert {r[1] for r in observations_of(user)} == {None, "dup"}
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT array_agg(rule_code ORDER BY rule_code) FROM data_quality_results WHERE sync_run_id = %s",
            (run["id"],),
        )
        assert cur.fetchone()[0] == ["bad_event_at", "duplicate_key", "out_of_range"]


def test_all_records_rejected_is_a_failed_run(user):
    only_bad = [
        Observation(
            "github",
            "github_repo_commit_count",
            -1,
            source_object_id="x",
            event_at=PUSHED,
            event_at_precision="repo_push",
        )
    ]
    with with_adapter(only_bad):
        run = user.sync().json()
    assert run["status"] == "failed" and run["safe_error_code"] == "all_rejected"
    assert observations_of(user) == []


def test_cooldown_applies_after_any_attempt_including_failures(user, monkeypatch):
    monkeypatch.setattr(config, "SYNC_COOLDOWN_SECONDS", 300)
    with with_adapter(ProviderError("unavailable")):
        assert user.sync().json()["status"] == "failed"
    with with_adapter(gh()) as m:
        r = user.sync()
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0 and m.call_count == 0


def test_second_sync_while_running_is_refused(user):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO sync_runs (connection_id, status, ingestion_version) "
            "SELECT id, 'running', 'x' FROM integration_connections WHERE user_id = (SELECT id FROM users WHERE auth_subject = %s) "
            "AND provider = 'github'",
            (user_obj_sub(user),),
        )
    with with_adapter(gh()) as m:
        r = user.sync()
    assert r.status_code == 409 and m.call_count == 0


def test_stale_running_row_is_abandoned_not_blocking_forever(user):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO sync_runs (connection_id, status, ingestion_version, started_at) "
            "SELECT id, 'running', 'x', now() - interval '1 hour' FROM integration_connections "
            "WHERE user_id = (SELECT id FROM users WHERE auth_subject = %s)",
            (user_obj_sub(user),),
        )
    with with_adapter(gh()):
        assert user.sync().json()["status"] == "succeeded"
    assert "abandoned" in [r["safe_error_code"] for r in user.runs()]


def test_guards_without_connection_or_profile():
    u = User()
    assert u.sync().status_code == 404  # no connection
    assert u.call("put", f"{V1}/integrations/github", json={"username": "octo"}).status_code == 200
    assert u.sync().status_code == 409  # connection but no profile


def test_leetcode_is_disabled_by_default():
    u = User()
    assert config.LEETCODE_INTEGRATION_ENABLED is False
    assert (
        u.call("put", f"{V1}/integrations/leetcode", json={"username": "someone"}).status_code
        == 503
    )
    assert u.sync("leetcode").status_code == 503


def test_leetcode_sync_stores_aggregates_without_event_times_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "LEETCODE_INTEGRATION_ENABLED", True)
    u = User()
    u.call("put", f"{V1}/me/profile", json={"display_name": "T"})
    assert (
        u.call("put", f"{V1}/integrations/leetcode", json={"username": "someone"}).status_code
        == 200
    )
    lc = [
        Observation("leetcode", f"leetcode_solved_{d}", n)
        for d, n in (("easy", 5), ("medium", 0), ("hard", 1))
    ]
    with patch("ingest.leetcode_api.fetch_leetcode_observations", return_value=(lc, False)):
        run = u.sync("leetcode").json()
    assert run["status"] == "succeeded"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT granularity, event_at IS NULL, event_at_precision FROM source_observations WHERE sync_run_id = %s",
            (run["id"],),
        )
        assert cur.fetchall() == [("aggregate", True, "unknown")]


@pytest.mark.parametrize("name", ["", "../x", "a b", "-lead", "x" * 70])
def test_bad_usernames_rejected(name):
    assert User().call("put", f"{V1}/integrations/github", json={"username": name}).status_code in (
        422,
    )


def test_changing_username_starts_a_new_connection_and_keeps_history(user):
    with with_adapter(gh(("a", 1))):
        user.sync()
    assert (
        user.call("put", f"{V1}/integrations/github", json={"username": "someone-else"}).status_code
        == 200
    )
    conns = user.call("get", f"{V1}/integrations").json()["items"]
    assert [c["external_username"] for c in conns] == ["someone-else"]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT external_username, status FROM integration_connections WHERE user_id = (SELECT id FROM users WHERE auth_subject = %s) ORDER BY connected_at",
            (user_obj_sub(user),),
        )
        assert cur.fetchall() == [("octo", "disconnected"), ("someone-else", "connected")]
    assert (
        len(observations_of(user)) == 2
    )  # old account's observations stay, traceable to the old connection


def test_other_users_cannot_see_or_trigger_my_runs(user):
    with with_adapter(gh(("a", 1))):
        user.sync()
    other = User()
    assert other.call("get", f"{V1}/integrations").json()["items"] == []
    assert other.call("get", f"{V1}/sync-runs?provider=github").json()["items"] == []
    assert other.sync().status_code == 404


def test_anonymous_is_rejected():
    assert client.get(f"{V1}/integrations").status_code == 401
    assert client.put(f"{V1}/integrations/github", json={"username": "x"}).status_code == 401
    assert client.post(f"{V1}/integrations/github/sync").status_code == 401
    assert client.get(f"{V1}/sync-runs?provider=github").status_code == 401


def test_unexpected_adapter_crash_still_closes_the_run(user, caplog):
    # whether TestClient re-raises the background-task error depends on the middleware stack, so the run row and log are the contract
    caplog.set_level("INFO", logger="pis")
    with patch("ingest.github_api.fetch_github_observations", side_effect=KeyError("boom")):
        try:
            user.sync()
        except KeyError:
            pass
    run = user.runs()[0]
    assert run["status"] == "failed"
    assert run["safe_error_code"] == "internal_error"
    assert run["completed_at"] is not None
    assert any(r.message == "sync_finished" and r.sync_status == "failed" for r in caplog.records)


# ── data-model invariants (provenance is enforced by the schema, not by convention) ──
def test_schema_rejects_observed_value_without_a_sync_run(user):
    with pytest.raises(psycopg2.errors.CheckViolation):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO source_observations (profile_id, provider, observation_type, provenance, granularity, "
                "value_num, payload_version) SELECT id, 'github', 'x', 'observed', 'aggregate', 1, 'v' FROM profiles "
                "WHERE user_id = (SELECT id FROM users WHERE auth_subject = %s)",
                (user_obj_sub(user),),
            )


@pytest.mark.parametrize(
    "cols,vals",
    [
        (
            "event_at_precision, value_num",
            "'exact', 1",
        ),  # an aggregate cannot claim an exact event time
        ("value_state, value_num", "'measured_zero', 3"),  # measured_zero must be 0
        ("value_state, value_num", "'present', NULL"),  # a present value needs a number
    ],
)
def test_schema_rejects_contradictory_observations(user, cols, vals):
    with pytest.raises(psycopg2.errors.CheckViolation):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO source_observations (profile_id, provider, observation_type, provenance, granularity, "
                f"payload_version, {cols}) SELECT id, 'github', 'x', 'user_entered', 'aggregate', 'v', {vals} FROM profiles "
                f"WHERE user_id = (SELECT id FROM users WHERE auth_subject = %s)",
                (user_obj_sub(user),),
            )
