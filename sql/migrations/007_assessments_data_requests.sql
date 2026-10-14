-- Phase 9: user-owned assessments (immutable snapshots) and export/deletion request tracking.
-- Real-user assessments are keyed by profile; the legacy students-keyed predictions tables are untouched.
CREATE TABLE assessments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id      UUID NOT NULL REFERENCES profiles(id),
    assessment_type TEXT NOT NULL CHECK (assessment_type IN ('insufficient_evidence','ml_readiness_proxy')),
    readiness_score NUMERIC(5,2) CHECK (readiness_score BETWEEN 0 AND 100),
    category        TEXT,
    reason          TEXT,
    model_version   TEXT,                       -- NULL when no model produced the result
    evidence        JSONB NOT NULL,             -- immutable input snapshot: values, provenance, sync run ids
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((assessment_type = 'ml_readiness_proxy') = (readiness_score IS NOT NULL))
);
CREATE INDEX idx_assessments_profile ON assessments(profile_id, created_at DESC);

CREATE FUNCTION assessments_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'assessments rows are immutable';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_assessments_immutable BEFORE UPDATE ON assessments
    FOR EACH ROW EXECUTE FUNCTION assessments_immutable();

-- Records the request only; nothing fulfils it yet (Phase 13), so status stays 'requested'.
CREATE TABLE data_requests (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id),
    kind         TEXT NOT NULL CHECK (kind IN ('export','deletion')),
    status       TEXT NOT NULL DEFAULT 'requested' CHECK (status IN ('requested','processing','completed','failed','cancelled')),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- One open request per kind per user: repeating the call is idempotent.
CREATE UNIQUE INDEX uq_open_data_request ON data_requests(user_id, kind) WHERE status IN ('requested','processing');
