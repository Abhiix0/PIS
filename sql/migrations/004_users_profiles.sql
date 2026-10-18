-- Phase 5 "expand" step (ADR-0001): identity + user-owned profiles beside the legacy students table.
-- Nothing is renamed or dropped; legacy students are NOT backfilled here and can never be owned by a user.
CREATE TYPE data_origin AS ENUM ('real','demo','legacy_seed');

CREATE TABLE users (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_subject         TEXT NOT NULL UNIQUE,          -- opaque IdP subject ("sub")
    email                TEXT,
    status               TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','deletion_pending','deleted')),
    sessions_valid_after TIMESTAMPTZ,                   -- tokens issued before this are revoked (sign-out)
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE profiles (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID UNIQUE REFERENCES users(id) ON DELETE RESTRICT,
    origin            data_origin NOT NULL,
    legacy_student_id INT UNIQUE,
    display_name      TEXT NOT NULL,
    branch            TEXT,
    graduation_year   SMALLINT,
    cgpa              NUMERIC(4,2) CHECK (cgpa BETWEEN 0 AND 10),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((origin = 'real') = (user_id IS NOT NULL))
);
