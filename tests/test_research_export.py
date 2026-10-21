"""Research consent gating and the operator export (ml.forecast.export). Need a migrated DB."""

import csv
import hashlib
import json
import uuid

from ingest.db_connection import fetch_all, get_connection
from ml.forecast import export
from tests.test_api_v1 import U


def _user(name="Zed Person", username="zed-octo"):
    u = U()
    pid = u.put("/me/profile", json={"display_name": name, "cgpa": 7}).json()["id"]
    u.put("/integrations/github", json={"username": username})
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM integration_connections WHERE external_username = %s", (username,)
        )
        conn_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO sync_runs (connection_id, status, ingestion_version) VALUES (%s, 'succeeded', 't') RETURNING id",
            (conn_id,),
        )
        run_id = cur.fetchone()[0]
        for prov, day, n in (("observed", "2026-01-01", 3), ("observed", "2026-01-02", 0)):
            _obs(cur, pid, run_id, prov, day, n)
        # synthetic rows must have no sync run (table CHECK)
        _obs(cur, pid, None, "synthetic", "2026-01-03", 9)
    return u, pid


def _obs(cur, pid, run_id, prov, day, n):
    cur.execute(
        "INSERT INTO source_observations (profile_id, sync_run_id, provider, observation_type, source_object_id, "
        "provenance, granularity, event_at, event_at_precision, value_num, value_state, payload_version) "
        "VALUES (%s, %s, 'github', 'github_contribution_day', %s, %s, 'event', %s, 'day', %s, %s, 't')",
        (pid, run_id, day, prov, f"{day}T00:00:00Z", n, "measured_zero" if n == 0 else "present"),
    )


def _run(tmp_path):
    m = export.run(tmp_path)
    with open(tmp_path / m["file"], newline="", encoding="utf-8") as f:
        return m, list(csv.DictReader(f))


def test_nothing_is_exported_without_consent(tmp_path):
    u, _ = _user(username=f"nc-{uuid.uuid4().hex[:8]}")
    before = _run(tmp_path)[0]["rows"]
    u.put("/me/privacy", json={"research": True})
    assert _run(tmp_path)[0]["rows"] == before + 2


def test_revoke_excludes_from_next_export_and_is_audited(tmp_path):
    u, _ = _user(username=f"rv-{uuid.uuid4().hex[:8]}")
    base = _run(tmp_path)[0]["rows"]
    u.put("/me/privacy", json={"research": True})
    assert _run(tmp_path)[0]["rows"] == base + 2
    u.put("/me/privacy", json={"research": False})
    assert _run(tmp_path)[0]["rows"] == base
    actions = [
        r["action"]
        for r in fetch_all("SELECT action FROM audit_events ORDER BY created_at DESC LIMIT 200")
    ]
    assert "consent.research_granted" in actions and "consent.research_revoked" in actions


def test_export_has_no_pii_only_observed_and_matching_sha(tmp_path):
    name, username = "Zed Person", f"pii-{uuid.uuid4().hex[:8]}"
    u, pid = _user(name, username)
    u.put("/me/privacy", json={"research": True})
    m, rows = _run(tmp_path)
    raw = (tmp_path / m["file"]).read_bytes()
    text = raw.decode("utf-8")
    uid = fetch_all("SELECT user_id::text AS u FROM profiles WHERE id = %s", (pid,))[0]["u"]
    for secret in (name, username, uid, pid, "@"):
        assert secret not in text
    assert list(rows[0]) == export.COLUMNS
    assert "2026-01-03" not in text  # synthetic row excluded
    assert m["data_sha256"] == hashlib.sha256(raw).hexdigest()
    assert m["rows"] == len(rows) and "email" not in json.dumps(m)


def test_pseudo_ids_differ_between_exports(tmp_path):
    u, _ = _user(username=f"ps-{uuid.uuid4().hex[:8]}")
    u.put("/me/privacy", json={"research": True})
    a, b = _run(tmp_path)[1], _run(tmp_path)[1]
    assert {r["pseudo_id"] for r in a}.isdisjoint({r["pseudo_id"] for r in b})


def test_cli_refuses_without_confirmation_flag(tmp_path, capsys):
    assert export.main(["--out", str(tmp_path)]) == 2
    assert list(tmp_path.iterdir()) == []
    assert export.main(["--out", str(tmp_path), export.CONFIRM_FLAG]) == 0


def test_cli_has_no_api_route():
    from app.main import app

    assert not any("research" in getattr(r, "path", "") and "export" in r.path for r in app.routes)
