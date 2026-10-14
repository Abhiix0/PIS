-- Migration 001a: unique key required by GitHub ingestion's ON CONFLICT target.
-- Dedupes first so the upgrade also works on databases that already hold duplicate rows.
DELETE FROM github_activity a
USING github_activity b
WHERE a.id > b.id
  AND a.student_id = b.student_id AND a.repo_name = b.repo_name AND a.commit_date = b.commit_date;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_github_activity') THEN
        ALTER TABLE github_activity
            ADD CONSTRAINT uq_github_activity UNIQUE (student_id, repo_name, commit_date);
    END IF;
END $$;
