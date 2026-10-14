-- Phase 4 DRAFT target schema. NOT a migration: not in sql/migrations/, never applied by the runner.
-- Phase 5/6 split this into numbered migrations. Checked only for syntax on a scratch database.
CREATE TYPE provenance AS ENUM ('observed','user_entered','derived','inferred','synthetic');
CREATE TYPE value_state AS ENUM ('present','not_collected','source_failed','stale','measured_zero');
CREATE TYPE data_origin AS ENUM ('real','demo','legacy_seed');

CREATE TABLE users (
    id           UUID PRIMARY KEY,
    auth_subject TEXT NOT NULL UNIQUE,            -- opaque IdP subject; provider chosen in Phase 5 (PRD 19#2)
    email        TEXT,
    status       TEXT NOT NULL CHECK (status IN ('active','suspended','deletion_pending','deleted')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE profiles (
    id                UUID PRIMARY KEY,
    user_id           UUID UNIQUE REFERENCES users(id) ON DELETE RESTRICT,
    origin            data_origin NOT NULL,
    legacy_student_id INT UNIQUE,                 -- link to students.id; dropped after Phase 5 cutover
    display_name      TEXT NOT NULL,
    branch            TEXT,
    graduation_year   SMALLINT,
    cgpa              NUMERIC(4,2) CHECK (cgpa BETWEEN 0 AND 10),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- demo/legacy rows can never be owned by an account; real rows must be.
    CHECK ((origin = 'real') = (user_id IS NOT NULL))
);

CREATE TABLE integration_connections (
    id                UUID PRIMARY KEY,
    user_id           UUID NOT NULL REFERENCES users(id),
    provider          TEXT NOT NULL CHECK (provider IN ('github','leetcode')),
    external_username TEXT NOT NULL,
    status            TEXT NOT NULL CHECK (status IN ('connected','disconnected','error')),
    secret_ref        TEXT,                       -- reference into a secret store; never a token
    connected_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_attempt_at   TIMESTAMPTZ,
    last_success_at   TIMESTAMPTZ,
    disconnected_at   TIMESTAMPTZ
);
CREATE UNIQUE INDEX uq_active_connection ON integration_connections(user_id, provider) WHERE status <> 'disconnected';

CREATE TABLE sync_runs (
    id                UUID PRIMARY KEY,
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

CREATE TABLE source_observations (
    id                 UUID PRIMARY KEY,
    profile_id         UUID NOT NULL REFERENCES profiles(id),
    sync_run_id        UUID REFERENCES sync_runs(id),   -- NULL only for user_entered / synthetic
    provider           TEXT NOT NULL,
    observation_type   TEXT NOT NULL,                   -- e.g. 'github_repo_commit_count', 'leetcode_solved_total'
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
    CHECK (granularity = 'event' OR event_at_precision IS DISTINCT FROM 'exact'),
    CHECK ((value_state IN ('present','measured_zero','stale')) = (value_num IS NOT NULL))
);
CREATE INDEX idx_obs_profile_type ON source_observations(profile_id, observation_type, collected_at DESC);

CREATE TABLE data_quality_results (
    id             UUID PRIMARY KEY,
    sync_run_id    UUID NOT NULL REFERENCES sync_runs(id),
    observation_id UUID REFERENCES source_observations(id),
    rule_code      TEXT NOT NULL,
    outcome        TEXT NOT NULL CHECK (outcome IN ('passed','warned','rejected')),
    detail         TEXT,
    checked_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE feature_schemas (
    version    TEXT PRIMARY KEY,
    definition JSONB NOT NULL,                        -- feature names, units, formulas, window, scaling
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE feature_snapshots (
    id                     UUID PRIMARY KEY,
    profile_id             UUID NOT NULL REFERENCES profiles(id),
    feature_schema_version TEXT NOT NULL REFERENCES feature_schemas(version),
    as_of                  TIMESTAMPTZ NOT NULL,      -- observation-window end the features were computed for
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_coverage        JSONB NOT NULL,
    quality_summary        JSONB NOT NULL
);
CREATE TABLE feature_values (                         -- normalised: provenance is queryable, not buried in JSON
    snapshot_id  UUID NOT NULL REFERENCES feature_snapshots(id),
    feature_name TEXT NOT NULL,
    value_num    NUMERIC,
    state        value_state NOT NULL,
    provenance   provenance NOT NULL,
    PRIMARY KEY (snapshot_id, feature_name),
    CHECK ((state IN ('present','measured_zero','stale')) = (value_num IS NOT NULL)),
    CHECK (state <> 'measured_zero' OR value_num = 0)
);
CREATE TABLE snapshot_inputs (                        -- exactly which observations fed a snapshot
    snapshot_id    UUID NOT NULL REFERENCES feature_snapshots(id),
    observation_id UUID NOT NULL REFERENCES source_observations(id),
    PRIMARY KEY (snapshot_id, observation_id)
);

CREATE TABLE model_versions (
    id                     UUID PRIMARY KEY,
    name                   TEXT NOT NULL,
    version                TEXT NOT NULL,
    kind                   TEXT NOT NULL CHECK (kind IN ('rule','ml')),
    feature_schema_version TEXT NOT NULL REFERENCES feature_schemas(version),
    artifact_ref           TEXT,
    artifact_sha256        TEXT,
    training_dataset_ref   TEXT,
    code_revision          TEXT,
    metrics_summary        JSONB,
    approval_status        TEXT NOT NULL CHECK (approval_status IN ('candidate','approved','rejected','retired')),
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, version),
    CHECK (kind = 'rule' OR (artifact_ref IS NOT NULL AND artifact_sha256 IS NOT NULL))
);
CREATE TABLE model_activations (                      -- append-only activation log
    id               UUID PRIMARY KEY,
    model_version_id UUID NOT NULL REFERENCES model_versions(id),
    action           TEXT NOT NULL CHECK (action IN ('activate','deactivate','rollback')),
    actor_user_id    UUID REFERENCES users(id),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE assessments (                            -- immutable: no UPDATE path
    id                     UUID PRIMARY KEY,
    profile_id             UUID NOT NULL REFERENCES profiles(id),
    feature_snapshot_id    UUID NOT NULL REFERENCES feature_snapshots(id),
    model_version_id       UUID NOT NULL REFERENCES model_versions(id),
    assessment_type        TEXT NOT NULL,
    output_payload_version TEXT NOT NULL,
    score                  NUMERIC(5,2) CHECK (score BETWEEN 0 AND 100),
    interpretation         TEXT NOT NULL,
    quality_warnings       JSONB NOT NULL DEFAULT '[]',
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE assessment_evidence (
    assessment_id UUID NOT NULL REFERENCES assessments(id),
    feature_name  TEXT NOT NULL,
    contribution  NUMERIC,
    PRIMARY KEY (assessment_id, feature_name)
);
CREATE TABLE recommendations (
    id               UUID PRIMARY KEY,
    assessment_id    UUID NOT NULL REFERENCES assessments(id),
    rule_code        TEXT NOT NULL,
    priority         SMALLINT NOT NULL,
    evidence_feature TEXT,
    explanation      TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE recommendation_states (                  -- mutable action state kept apart from the immutable recommendation
    recommendation_id UUID PRIMARY KEY REFERENCES recommendations(id),
    status            TEXT NOT NULL CHECK (status IN ('planned','in_progress','completed','dismissed')),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_events (
    id            UUID PRIMARY KEY,
    actor_user_id UUID REFERENCES users(id),          -- NULL = system/worker
    actor_kind    TEXT NOT NULL CHECK (actor_kind IN ('user','operator','worker','system')),
    event_type    TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id   TEXT,
    request_id    TEXT,
    metadata      JSONB NOT NULL DEFAULT '{}',        -- never credentials or raw payloads
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE data_requests (
    id           UUID PRIMARY KEY,
    user_id      UUID NOT NULL REFERENCES users(id),
    kind         TEXT NOT NULL CHECK (kind IN ('export','deletion')),
    status       TEXT NOT NULL CHECK (status IN ('requested','processing','completed','failed')),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);
