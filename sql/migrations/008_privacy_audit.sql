-- Phase 13: audit trail and optional research consent.
-- audit_events holds ids and action names only (never tokens, usernames or profile values) and survives account deletion.
CREATE TABLE audit_events (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id UUID REFERENCES users(id),     -- NULL for system actors; operators are recorded by their IdP subject below
    actor_subject TEXT,
    action        TEXT NOT NULL,
    target        TEXT,                          -- e.g. a model version or provider name; never personal data
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_created ON audit_events(created_at DESC);

CREATE FUNCTION audit_events_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_events rows are append-only';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_audit_events_immutable BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();

-- NULL = never opted in. Nothing in the system reads this yet: no training use of real-user data exists.
ALTER TABLE users ADD COLUMN research_consent_at TIMESTAMPTZ;
