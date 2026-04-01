-- ============================================
-- PIS Database Schema
-- Run: psql -U pis_user -d pis_db -f sql/schema.sql
-- ============================================

CREATE TABLE IF NOT EXISTS students (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(150) UNIQUE NOT NULL,
    cgpa        NUMERIC(4,2) CHECK (cgpa BETWEEN 0 AND 10),
    branch      VARCHAR(50) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS coding_activity (
    id          SERIAL PRIMARY KEY,
    student_id  INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    problem_id  VARCHAR(50) NOT NULL,
    difficulty  VARCHAR(10) NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard')),
    solved_at   DATE NOT NULL CHECK (solved_at <= CURRENT_DATE),
    UNIQUE (student_id, problem_id)  -- no duplicate solves
);

CREATE TABLE IF NOT EXISTS github_activity (
    id          SERIAL PRIMARY KEY,
    student_id  INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    repo_name   VARCHAR(150) NOT NULL,
    commits     INT NOT NULL CHECK (commits > 0),
    commit_date DATE NOT NULL CHECK (commit_date <= CURRENT_DATE)
);

CREATE TABLE IF NOT EXISTS features (
    student_id        INT PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
    total_problems    INT DEFAULT 0,
    avg_difficulty    NUMERIC(4,2) DEFAULT 0,
    commit_frequency  NUMERIC(6,4) DEFAULT 0,
    consistency_score NUMERIC(4,3) DEFAULT 0,
    computed_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS predictions (
    student_id      INT PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
    readiness_score NUMERIC(5,2) CHECK (readiness_score BETWEEN 0 AND 100),
    category        VARCHAR(20) CHECK (category IN (
                        'Ready', 'Near Ready', 'Needs Improvement')),
    last_updated    TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes: added on columns used in JOINs, WHERE, and ORDER BY

CREATE INDEX IF NOT EXISTS idx_coding_student  ON coding_activity(student_id);
CREATE INDEX IF NOT EXISTS idx_coding_date      ON coding_activity(solved_at);
CREATE INDEX IF NOT EXISTS idx_github_student   ON github_activity(student_id);
CREATE INDEX IF NOT EXISTS idx_github_date      ON github_activity(commit_date);
CREATE INDEX IF NOT EXISTS idx_students_branch  ON students(branch);

-- Add to sql/schema.sql — these cover the most common access patterns

-- Partial index: only index recent coding activity (last 90 days)
-- Much smaller than a full index, same benefit for consistency_score query
CREATE INDEX IF NOT EXISTS idx_coding_recent
    ON coding_activity(student_id, solved_at)
    WHERE solved_at >= CURRENT_DATE - INTERVAL '90 days';

-- Composite index for the github frequency query
CREATE INDEX IF NOT EXISTS idx_github_student_date
    ON github_activity(student_id, commit_date);

-- Covering index on features — avoids heap fetch for the most common read
CREATE INDEX IF NOT EXISTS idx_features_covering
    ON features(student_id)
    INCLUDE (total_problems, avg_difficulty, consistency_score, commit_frequency);

-- Migration 001: platform usernames
ALTER TABLE students ADD COLUMN IF NOT EXISTS github_username VARCHAR(100);
ALTER TABLE students ADD COLUMN IF NOT EXISTS leetcode_username VARCHAR(100);

-- Migration 002: API sync timestamps for staleness checks
ALTER TABLE students ADD COLUMN IF NOT EXISTS github_last_synced   TIMESTAMPTZ;
ALTER TABLE students ADD COLUMN IF NOT EXISTS leetcode_last_synced TIMESTAMPTZ;

-- Migration 003: Prediction history for score velocity tracking
CREATE TABLE IF NOT EXISTS prediction_history (
    id              SERIAL PRIMARY KEY,
    student_id      INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    readiness_score NUMERIC(5,2) NOT NULL,
    category        VARCHAR(20)  NOT NULL,
    recorded_at     TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pred_history_student_time
    ON prediction_history(student_id, recorded_at DESC);