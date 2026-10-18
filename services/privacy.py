"""User-initiated data control: export, source-data removal, account deletion, and the audit trail."""

from typing import Any

from ingest.db_connection import get_connection

_EXPORT_FORMAT = "pis-export-v1"


def _dicts(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def audit(
    cur,
    action: str,
    user_id: str | None = None,
    subject: str | None = None,
    target: str | None = None,
) -> None:
    """Append an audit event on the caller's cursor, so it commits atomically with the action it records."""
    cur.execute(
        "INSERT INTO audit_events (actor_user_id, actor_subject, action, target) VALUES (%s, %s, %s, %s)",
        (user_id, subject, action, target),
    )


def delete_source_data(cur, user_id: str, provider: str) -> int:
    """Remove imported observations (and their quality records) for one provider. Sync-run metadata is kept."""
    cur.execute(
        "DELETE FROM data_quality_results WHERE observation_id IN (SELECT o.id FROM source_observations o "
        "JOIN profiles p ON p.id = o.profile_id WHERE p.user_id = %s AND o.provider = %s)",
        (user_id, provider),
    )
    cur.execute(
        "DELETE FROM data_quality_results WHERE sync_run_id IN (SELECT r.id FROM sync_runs r "
        "JOIN integration_connections c ON c.id = r.connection_id WHERE c.user_id = %s AND c.provider = %s)",
        (user_id, provider),
    )
    cur.execute(
        "DELETE FROM source_observations WHERE provider = %s AND profile_id IN "
        "(SELECT id FROM profiles WHERE user_id = %s)",
        (provider, user_id),
    )
    return cur.rowcount


def export_data(user_id: str) -> dict:
    """Everything stored about the user, as JSON-serialisable dicts. No tokens exist to leak; none are stored."""
    q = {
        "profile": "SELECT display_name, branch, graduation_year, cgpa::float AS cgpa, created_at, updated_at "
        "FROM profiles WHERE user_id = %s",
        "integrations": "SELECT provider, external_username, status, connected_at, last_success_at, disconnected_at "
        "FROM integration_connections WHERE user_id = %s ORDER BY connected_at",
        "sync_runs": "SELECT c.provider, r.status, r.started_at, r.completed_at, r.records_created, r.records_rejected, "
        "r.safe_error_code, r.ingestion_version FROM sync_runs r JOIN integration_connections c "
        "ON c.id = r.connection_id WHERE c.user_id = %s ORDER BY r.started_at",
        "observations": "SELECT o.provider, o.observation_type, o.source_object_id, o.provenance::text AS provenance, "
        "o.granularity, o.event_at, o.event_at_precision, o.collected_at, o.value_num::float AS value_num, "
        "o.value_state::text AS value_state, o.quality_status FROM source_observations o "
        "JOIN profiles p ON p.id = o.profile_id WHERE p.user_id = %s ORDER BY o.collected_at",
        "assessments": "SELECT a.id::text AS id, a.assessment_type, a.readiness_score::float AS readiness_score, "
        "a.category, a.reason, a.model_version, a.evidence, a.created_at FROM assessments a "
        "JOIN profiles p ON p.id = a.profile_id WHERE p.user_id = %s ORDER BY a.created_at",
        "data_requests": "SELECT kind, status, requested_at, updated_at FROM data_requests WHERE user_id = %s "
        "ORDER BY requested_at",
    }
    with get_connection() as conn, conn.cursor() as cur:
        out: dict[str, Any] = {}
        for key, sql in q.items():
            cur.execute(sql, (user_id,))
            out[key] = _dicts(cur)
        out["profile"] = out["profile"][0] if out["profile"] else None
        cur.execute(
            "SELECT email, research_consent_at, created_at FROM users WHERE id = %s", (user_id,)
        )
        out["account"] = _dicts(cur)[0]
        cur.execute(
            "INSERT INTO data_requests (user_id, kind, status) VALUES (%s, 'export', 'completed')",
            (user_id,),
        )
        audit(cur, "export.completed", user_id)
    return {"format": _EXPORT_FORMAT, **out}


def delete_account(user_id: str) -> dict:
    """Erase the user's personal data and lock the account. Keeps a tombstone `users` row (subject, no email) so the
    same IdP identity cannot silently start a new account with the old sessions, plus audit and request records."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE id = %s FOR UPDATE", (user_id,))
        for provider in ("github", "leetcode"):
            delete_source_data(cur, user_id, provider)
        cur.execute(
            "DELETE FROM sync_runs WHERE connection_id IN (SELECT id FROM integration_connections WHERE user_id = %s)",
            (user_id,),
        )
        cur.execute("DELETE FROM integration_connections WHERE user_id = %s", (user_id,))
        cur.execute(
            "DELETE FROM assessments WHERE profile_id IN (SELECT id FROM profiles WHERE user_id = %s)",
            (user_id,),
        )
        cur.execute("DELETE FROM profiles WHERE user_id = %s", (user_id,))
        cur.execute(
            "UPDATE users SET status = 'deleted', email = NULL, research_consent_at = NULL, "
            "sessions_valid_after = now(), updated_at = now() WHERE id = %s",
            (user_id,),
        )
        cur.execute(
            "INSERT INTO data_requests (user_id, kind, status) VALUES (%s, 'deletion', 'completed') "
            "RETURNING id::text, kind, status, requested_at, updated_at",
            (user_id,),
        )
        req = _dicts(cur)[0]
        audit(cur, "account.deleted", user_id)
    return req
