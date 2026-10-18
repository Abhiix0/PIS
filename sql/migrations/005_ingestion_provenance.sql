-- Phase 6: provenance-aware observations and the sync lifecycle (ADR-0002, docs/phase4/draft-schema.sql).
-- Real-user provider data lives only in source_observations; the legacy per-student tables stay demo-only.
CREATE TYPE provenance  AS ENUM ('observed','user_entered','derived','inferred','synthetic');
CREATE TYPE value_state AS ENUM ('present','not_collected','source_failed','stale','measured_zero');

-- Every legacy activity row is synthetic unless an adapter says otherwise (seed + generators rely on the default).
ALTER TABLE coding_activity ADD COLUMN provenance provenance NOT NULL DEFAULT 'synthetic';
ALTER TABLE github_activity ADD COLUMN provenance provenance NOT NULL DEFAULT 'synthetic';

CREATE TABLE integration_connections (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(id),
    provider          TEXT NOT NULL CHECK (provider IN ('github','leetcode')),
    external_username TEXT NOT NULL,                 -- public username only; no token or secret is ever stored
    status            TEXT NOT NULL DEFAULT 'connected' CHECK (status IN ('connected','disconnected','error')),
    connected_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_attempt_at   TIMESTAMPTZ,
    last_success_at   TIMESTAMPTZ,
    disconnected_at   TIMESTAMPTZ
);
CREATE UNIQUE INDEX uq_active_connection ON integration_connections(user_id, provider) WHERE status <> 'disconnected';

CREATE TABLE sync_runs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id     UUID NOT NULL REFERENCES integration_connections(id),
    status            TEXT NOT NULL CHECK (status IN ('running','succeeded','partial','failed')),
    started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at      TIMESTAMPTZ,
    records_observed  INT,
    records_created   INT,
    records_rejected  INT,
    safe_error_code   TEXT,
    ingestion_version TEXT NOT NULL
);
CREATE INDEX idx_sync_runs_conn ON sync_runs(connection_id, started_at DESC);
-- At most one in-flight run per connection, enforced by the database rather than by timing.
CREATE UNIQUE INDEX uq_one_running_sync ON sync_runs(connection_id) WHERE status = 'running';

CREATE TABLE source_observations (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id         UUID NOT NULL REFERENCES profiles(id),
    sync_run_id        UUID REFERENCES sync_runs(id),   -- NULL only for user_entered / synthetic
    provider           TEXT NOT NULL,
    observation_type   TEXT NOT NULL,
    source_object_id   TEXT,
    provenance         provenance NOT NULL,
    granularity        TEXT NOT NULL CHECK (granularity IN ('event','aggregate')),
    event_at           TIMESTAMPTZ,                     -- when it happened at the source; NULL if unknown. Never filled from collected_at.
    event_at_precision TEXT CHECK (event_at_precision IN ('exact','day','repo_push','unknown')),
    collected_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    value_num          NUMERIC,
    value_state        value_state NOT NULL DEFAULT 'present',
    payload_version    TEXT NOT NULL,
    quality_status     TEXT NOT NULL DEFAULT 'unchecked' CHECK (quality_status IN ('unchecked','passed','warned','rejected')),
    CHECK (provenance <> 'synthetic' OR sync_run_id IS NULL),
    CHECK (provenance <> 'observed' OR sync_run_id IS NOT NULL),
    CHECK (granularity = 'event' OR event_at_precision IS DISTINCT FROM 'exact'),
    CHECK ((value_state IN ('present','measured_zero','stale')) = (value_num IS NOT NULL)),
    CHECK (value_state <> 'measured_zero' OR value_num = 0)
);
CREATE INDEX idx_obs_profile_type ON source_observations(profile_id, observation_type, collected_at DESC);
-- Retrying the same run cannot duplicate a row.
CREATE UNIQUE INDEX uq_obs_per_run ON source_observations(sync_run_id, observation_type, COALESCE(source_object_id, ''));

-- Rejected/warned records are kept here with a reason instead of being stored as values or dropped silently.
CREATE TABLE data_quality_results (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sync_run_id    UUID NOT NULL REFERENCES sync_runs(id),
    observation_id UUID REFERENCES source_observations(id),
    rule_code      TEXT NOT NULL,
    outcome        TEXT NOT NULL CHECK (outcome IN ('passed','warned','rejected')),
    detail         TEXT,
    checked_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_dq_run ON data_quality_results(sync_run_id);
