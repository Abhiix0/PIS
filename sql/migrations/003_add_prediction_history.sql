-- Migration 003: Prediction history for score velocity tracking
-- Run: psql -U pis_user -d pis_db -f sql/migrations/003_add_prediction_history.sql
CREATE TABLE IF NOT EXISTS prediction_history (
    id              SERIAL PRIMARY KEY,
    student_id      INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    readiness_score NUMERIC(5,2) NOT NULL,
    category        VARCHAR(20)  NOT NULL,
    recorded_at     TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pred_history_student_time
    ON prediction_history(student_id, recorded_at DESC);
