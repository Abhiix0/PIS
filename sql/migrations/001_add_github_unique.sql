ALTER TABLE github_activity ADD CONSTRAINT uq_github_activity UNIQUE (student_id, repo_name, commit_date);
