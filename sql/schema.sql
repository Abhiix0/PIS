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