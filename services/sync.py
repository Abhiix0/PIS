"""Sync lifecycle for real users: connect a public username, run a sync, read status.

A sync_run row is committed BEFORE the provider is called, so a crash still leaves a trace. Observations are
append-only: a failed or partial sync adds nothing that replaces earlier data, so last-known-good survives.
"""

import psycopg2

import config
from app.logger import logger
from ingest import github_api, leetcode_api
from ingest.db_connection import get_connection
from ingest.provider import ProviderError
from ingest.validators import validate_observation
from services import privacy

INGESTION_VERSION = "ingest-v1"
_STALE_RUN_MINUTES = 15  # a 'running' row older than this is a dead worker, not a live sync

_ADAPTERS = {  # looked up at call time so tests can patch the fetchers
    "github": (lambda u: github_api.fetch_github_observations(u), github_api.USERNAME_RE),
    "leetcode": (lambda u: leetcode_api.fetch_leetcode_observations(u), leetcode_api.USERNAME_RE),
}


class SyncRefused(Exception):
    """A request we decline before touching a provider; carries the HTTP status to return."""

    def __init__(self, status: int, detail: str, retry_after: int | None = None):
        super().__init__(detail)
        self.status, self.detail, self.retry_after = status, detail, retry_after


def _dicts(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _check_enabled(provider: str) -> None:
    if provider == "leetcode" and not config.LEETCODE_INTEGRATION_ENABLED:
        raise SyncRefused(
            503, "LeetCode integration is disabled: no official API and unverified terms."
        )


def connect(user_id: str, provider: str, username: str) -> dict:
    _check_enabled(provider)
    if not _ADAPTERS[provider][1].match(username):
        raise SyncRefused(422, f"Not a valid {provider} username.")
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, external_username FROM integration_connections "
                "WHERE user_id = %s AND provider = %s AND status <> 'disconnected' FOR UPDATE",
                (user_id, provider),
            )
            row = cur.fetchone()
            if row and row[1] == username:
                cid = row[0]
            else:
                if row:  # a different account must not feed the same series: keep the old connection as history
                    cur.execute(
                        "UPDATE integration_connections SET status = 'disconnected', disconnected_at = now() "
                        "WHERE id = %s",
                        (row[0],),
                    )
                cur.execute(
                    "INSERT INTO integration_connections (user_id, provider, external_username) "
                    "VALUES (%s, %s, %s) RETURNING id",
                    (user_id, provider, username),
                )
                cid = cur.fetchone()[0]
            return _connection(cur, cid)
    except psycopg2.errors.UniqueViolation:
        raise SyncRefused(409, "Connection changed concurrently; retry.") from None


def disconnect(user_id: str, provider: str, delete_data: bool = False) -> None:
    """Stop syncing (no provider token is ever stored, so there is nothing to revoke). Imported observations are
    kept as history unless `delete_data`; existing assessment snapshots are immutable and are never altered."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE integration_connections SET status = 'disconnected', disconnected_at = now() "
            "WHERE user_id = %s AND provider = %s AND status <> 'disconnected'",
            (user_id, provider),
        )
        if not cur.rowcount:
            raise SyncRefused(404, "No active connection for this provider.")
        if delete_data:
            privacy.delete_source_data(cur, user_id, provider)
        privacy.audit(
            cur,
            "integration.disconnected_and_data_deleted"
            if delete_data
            else "integration.disconnected",
            user_id,
            target=provider,
        )


def _connection(cur, cid) -> dict:
    cur.execute(
        "SELECT id::text AS id, provider, external_username, status, connected_at, last_attempt_at, "
        "last_success_at FROM integration_connections WHERE id = %s",
        (cid,),
    )
    return _dicts(cur)[0]


def _begin_run(user_id: str, provider: str) -> tuple[str, str, str, str]:
    """Guard + create the 'running' row. Returns (run_id, connection_id, profile_id, username)."""
    _check_enabled(provider)
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT c.id, c.external_username, p.id FROM integration_connections c "
                "LEFT JOIN profiles p ON p.user_id = c.user_id "
                "WHERE c.user_id = %s AND c.provider = %s AND c.status <> 'disconnected' FOR UPDATE OF c",
                (user_id, provider),
            )
            row = cur.fetchone()
            if not row:
                raise SyncRefused(404, f"No {provider} connection. Connect a username first.")
            cid, username, pid = row
            if not pid:
                raise SyncRefused(409, "Create a profile before syncing.")
            cur.execute(
                "UPDATE sync_runs SET status = 'failed', completed_at = now(), safe_error_code = 'abandoned' "
                "WHERE connection_id = %s AND status = 'running' "
                "AND started_at < now() - make_interval(mins => %s)",
                (cid, _STALE_RUN_MINUTES),
            )
            cur.execute(
                "SELECT GREATEST(0, %s - EXTRACT(EPOCH FROM now() - max(started_at))) FROM sync_runs "
                "WHERE connection_id = %s",
                (config.SYNC_COOLDOWN_SECONDS, cid),
            )
            wait = cur.fetchone()[0]
            if wait and wait > 0:
                raise SyncRefused(429, "Synced too recently.", retry_after=int(wait) + 1)
            cur.execute(
                "INSERT INTO sync_runs (connection_id, status, ingestion_version) "
                "VALUES (%s, 'running', %s) RETURNING id",
                (cid, INGESTION_VERSION),
            )
            rid = cur.fetchone()[0]
            cur.execute(
                "UPDATE integration_connections SET last_attempt_at = now() WHERE id = %s", (cid,)
            )
            return str(rid), str(cid), str(pid), username
    except psycopg2.errors.UniqueViolation:  # uq_one_running_sync
        raise SyncRefused(409, "A sync is already running.") from None


def _finish(
    run_id: str, cid: str, status: str, code=None, observed=None, created=None, rejected=None
) -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE sync_runs SET status = %s, completed_at = now(), safe_error_code = %s, "
            "records_observed = %s, records_created = %s, records_rejected = %s WHERE id = %s",
            (status, code, observed, created, rejected, run_id),
        )
        ok = status in ("succeeded", "partial")
        cur.execute(
            "UPDATE integration_connections SET status = %s, "
            "last_success_at = CASE WHEN %s THEN now() ELSE last_success_at END WHERE id = %s",
            ("connected" if ok else "error", ok, cid),
        )
    # alarm source: a metric filter on sync_status=failed drives the repeated-failure alert
    logger.info(
        "sync_finished", extra={"run_id": str(run_id), "sync_status": status, "error_code": code}
    )


def _store(run_id: str, pid: str, provider: str, observations) -> tuple[int, int]:
    """Validate and insert in one transaction. Returns (created, rejected); rejects are traced, never zeroed."""
    created = rejected = 0
    with get_connection() as conn, conn.cursor() as cur:
        for o in observations:
            reason = None
            try:
                validate_observation(o)
            except ValueError as e:
                reason = str(e)
            if reason is None:
                cur.execute(
                    "INSERT INTO source_observations (profile_id, sync_run_id, provider, observation_type, "
                    "source_object_id, provenance, granularity, event_at, event_at_precision, value_num, "
                    "value_state, payload_version, quality_status) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'passed') "
                    "ON CONFLICT (sync_run_id, observation_type, (COALESCE(source_object_id, ''))) DO NOTHING",
                    (
                        pid,
                        run_id,
                        provider,
                        o.observation_type,
                        o.source_object_id,
                        o.provenance,
                        o.granularity,
                        o.event_at,
                        o.event_at_precision,
                        o.value_num,
                        o.value_state,
                        o.payload_version,
                    ),
                )
                if cur.rowcount == 1:
                    created += 1
                    continue
                reason = "duplicate_key: same type and source id twice in one run"
            code, _, detail = reason.partition(": ")
            rejected += 1
            cur.execute(
                "INSERT INTO data_quality_results (sync_run_id, rule_code, outcome, detail) "
                "VALUES (%s, %s, 'rejected', %s)",
                (run_id, code, f"{o.observation_type} {o.source_object_id or ''}: {detail}"[:300]),
            )
    return created, rejected


def start_sync(user_id: str, provider: str) -> tuple[str, tuple]:
    """Guards + 'running' row only; the caller runs execute_run later (e.g. as a background task)."""
    run_id, *job = _begin_run(user_id, provider)
    return run_id, (run_id, provider, *job)


def execute_run(run_id: str, provider: str, cid: str, pid: str, username: str) -> None:
    try:
        observations, partial = _ADAPTERS[provider][0](username)
        if not observations:
            raise ProviderError("malformed", "provider returned no observations")
        created, rejected = _store(run_id, pid, provider, observations)
        code: str | None
        if created == 0:
            status, code = "failed", "all_rejected"
        else:
            status, code = (
                ("partial" if partial or rejected else "succeeded"),
                ("partial_result" if partial else None),
            )
        _finish(run_id, cid, status, code, len(observations), created, rejected)
    except (
        ProviderError
    ) as e:  # nothing was written for this run; earlier observations are untouched
        _finish(run_id, cid, "failed", e.code)
    except Exception:
        _finish(run_id, cid, "failed", "internal_error")
        raise


_RUN_COLS = (
    "r.id::text AS id, c.provider, r.status, r.started_at, r.completed_at, r.records_observed, "
    "r.records_created, r.records_rejected, r.safe_error_code, r.ingestion_version"
)


def get_run(user_id: str, run_id: str) -> dict:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT {_RUN_COLS} FROM sync_runs r JOIN integration_connections c ON c.id = r.connection_id "
            "WHERE r.id = %s AND c.user_id = %s",
            (run_id, user_id),
        )
        return _dicts(cur)[0]


def list_connections(user_id: str) -> list[dict]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id::text AS id, provider, external_username, status, connected_at, last_attempt_at, "
            "last_success_at FROM integration_connections WHERE user_id = %s AND status <> 'disconnected' "
            "ORDER BY provider",
            (user_id,),
        )
        return _dicts(cur)


def list_runs(user_id: str, provider: str, limit: int) -> list[dict]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT {_RUN_COLS} FROM sync_runs r JOIN integration_connections c ON c.id = r.connection_id "
            "WHERE c.user_id = %s AND c.provider = %s ORDER BY r.started_at DESC LIMIT %s",
            (user_id, provider, limit),
        )
        return _dicts(cur)
