-- Migration 006: model bundle registry and assessment snapshots (Phase 8)
CREATE TABLE IF NOT EXISTS model_versions (
    version               TEXT PRIMARY KEY,
    bundle_path           TEXT NOT NULL,
    bundle_sha256         TEXT NOT NULL,
    feature_schema_version TEXT NOT NULL,
    feature_cols          JSONB NOT NULL,
    target_semantics      TEXT NOT NULL,
    metrics               JSONB NOT NULL DEFAULT '{}',
    smoke_test            JSONB NOT NULL DEFAULT '{}',
    status                TEXT NOT NULL DEFAULT 'candidate'
                          CHECK (status IN ('candidate','rejected','approved','active','retired')),
    code_revision         TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_by           TEXT,
    approved_at           TIMESTAMPTZ,
    approval_note         TEXT,
    activated_by          TEXT,
    activated_at          TIMESTAMPTZ
);
-- At most one active model: activation is a single transactional status swap.
CREATE UNIQUE INDEX IF NOT EXISTS uq_model_versions_active ON model_versions((status)) WHERE status = 'active';

ALTER TABLE prediction_history ALTER COLUMN readiness_score DROP NOT NULL;
ALTER TABLE prediction_history ALTER COLUMN category DROP NOT NULL;
ALTER TABLE prediction_history ADD COLUMN IF NOT EXISTS assessment_type TEXT NOT NULL DEFAULT 'ml_readiness_proxy';
ALTER TABLE prediction_history ADD COLUMN IF NOT EXISTS model_version TEXT;
ALTER TABLE prediction_history ADD COLUMN IF NOT EXISTS input_snapshot JSONB;
ALTER TABLE prediction_history ADD COLUMN IF NOT EXISTS reason TEXT;

ALTER TABLE predictions ADD COLUMN IF NOT EXISTS assessment_type TEXT NOT NULL DEFAULT 'ml_readiness_proxy';
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS model_version TEXT;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS input_snapshot JSONB;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS reason TEXT;

-- History rows are immutable snapshots (deletes still cascade from students).
CREATE OR REPLACE FUNCTION prediction_history_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'prediction_history rows are immutable';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prediction_history_immutable ON prediction_history;
CREATE TRIGGER trg_prediction_history_immutable BEFORE UPDATE ON prediction_history
    FOR EACH ROW EXECUTE FUNCTION prediction_history_immutable();
