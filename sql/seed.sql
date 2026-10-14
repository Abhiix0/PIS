-- sql/seed.sql
-- DEMO DATA ONLY. Loaded by `python -m ingest.migrate --seed` after migrations;
-- refused when APP_ENV is staging/production.

-- 8 students across 4 archetypes (2 per type)
INSERT INTO students (name, email, cgpa, branch) VALUES
  ('Aryan Mehta',   'aryan@pis.dev',   9.1, 'CSE'),
  ('Priya Sharma',  'priya@pis.dev',   8.7, 'CSE'),
  ('Rohan Das',     'rohan@pis.dev',   7.8, 'IT'),
  ('Sneha Iyer',    'sneha@pis.dev',   7.2, 'IT'),
  ('Karan Patel',   'karan@pis.dev',   6.9, 'ECE'),
  ('Divya Nair',    'divya@pis.dev',   7.5, 'ECE'),
  ('Amit Roy',      'amit@pis.dev',    5.8, 'MECH'),
  ('Fatima Khan',   'fatima@pis.dev',  6.1, 'MECH');

-- ── Student 1 (Aryan Mehta) — strong: 18 coding rows ─────────────────────────
INSERT INTO coding_activity (student_id, problem_id, difficulty, solved_at) VALUES
  (1, 'P010001', 'hard',   '2024-01-05'),
  (1, 'P010002', 'hard',   '2024-01-12'),
  (1, 'P010003', 'medium', '2024-01-20'),
  (1, 'P010004', 'hard',   '2024-02-03'),
  (1, 'P010005', 'medium', '2024-02-14'),
  (1, 'P010006', 'hard',   '2024-02-25'),
  (1, 'P010007', 'medium', '2024-03-08'),
  (1, 'P010008', 'hard',   '2024-03-19'),
  (1, 'P010009', 'hard',   '2024-04-01'),
  (1, 'P010010', 'medium', '2024-04-10'),
  (1, 'P010011', 'hard',   '2024-04-22'),
  (1, 'P010012', 'medium', '2024-05-05'),
  (1, 'P010013', 'hard',   '2024-05-18'),
  (1, 'P010014', 'easy',   '2024-06-01'),
  (1, 'P010015', 'hard',   '2024-06-15'),
  (1, 'P010016', 'medium', '2024-07-02'),
  (1, 'P010017', 'hard',   '2024-07-20'),
  (1, 'P010018', 'medium', '2024-08-05');

-- ── Student 2 (Priya Sharma) — strong: 16 coding rows ────────────────────────
INSERT INTO coding_activity (student_id, problem_id, difficulty, solved_at) VALUES
  (2, 'P020001', 'hard',   '2024-01-08'),
  (2, 'P020002', 'medium', '2024-01-18'),
  (2, 'P020003', 'hard',   '2024-02-01'),
  (2, 'P020004', 'medium', '2024-02-12'),
  (2, 'P020005', 'hard',   '2024-02-28'),
  (2, 'P020006', 'medium', '2024-03-10'),
  (2, 'P020007', 'hard',   '2024-03-25'),
  (2, 'P020008', 'easy',   '2024-04-05'),
  (2, 'P020009', 'hard',   '2024-04-18'),
  (2, 'P020010', 'medium', '2024-05-02'),
  (2, 'P020011', 'hard',   '2024-05-20'),
  (2, 'P020012', 'medium', '2024-06-08'),
  (2, 'P020013', 'hard',   '2024-06-22'),
  (2, 'P020014', 'medium', '2024-07-10'),
  (2, 'P020015', 'hard',   '2024-07-28'),
  (2, 'P020016', 'medium', '2024-08-10');

-- ── Student 3 (Rohan Das) — coder, weak GH: 13 coding rows ───────────────────
INSERT INTO coding_activity (student_id, problem_id, difficulty, solved_at) VALUES
  (3, 'P030001', 'medium', '2024-01-15'),
  (3, 'P030002', 'hard',   '2024-02-01'),
  (3, 'P030003', 'medium', '2024-02-20'),
  (3, 'P030004', 'hard',   '2024-03-05'),
  (3, 'P030005', 'medium', '2024-03-22'),
  (3, 'P030006', 'easy',   '2024-04-08'),
  (3, 'P030007', 'medium', '2024-04-25'),
  (3, 'P030008', 'hard',   '2024-05-12'),
  (3, 'P030009', 'medium', '2024-05-28'),
  (3, 'P030010', 'hard',   '2024-06-14'),
  (3, 'P030011', 'medium', '2024-07-01'),
  (3, 'P030012', 'easy',   '2024-07-18'),
  (3, 'P030013', 'medium', '2024-08-03');

-- ── Student 4 (Sneha Iyer) — coder, weak GH: 11 coding rows ──────────────────
INSERT INTO coding_activity (student_id, problem_id, difficulty, solved_at) VALUES
  (4, 'P040001', 'medium', '2024-01-20'),
  (4, 'P040002', 'hard',   '2024-02-08'),
  (4, 'P040003', 'medium', '2024-02-25'),
  (4, 'P040004', 'easy',   '2024-03-12'),
  (4, 'P040005', 'medium', '2024-03-28'),
  (4, 'P040006', 'hard',   '2024-04-15'),
  (4, 'P040007', 'medium', '2024-05-02'),
  (4, 'P040008', 'easy',   '2024-05-20'),
  (4, 'P040009', 'medium', '2024-06-06'),
  (4, 'P040010', 'hard',   '2024-06-24'),
  (4, 'P040011', 'medium', '2024-07-15');

-- ── Student 5 (Karan Patel) — GH-heavy, weak DSA: 7 coding rows ──────────────
INSERT INTO coding_activity (student_id, problem_id, difficulty, solved_at) VALUES
  (5, 'P050001', 'easy',   '2024-02-10'),
  (5, 'P050002', 'easy',   '2024-03-05'),
  (5, 'P050003', 'medium', '2024-04-01'),
  (5, 'P050004', 'easy',   '2024-05-10'),
  (5, 'P050005', 'easy',   '2024-06-08'),
  (5, 'P050006', 'medium', '2024-07-03'),
  (5, 'P050007', 'easy',   '2024-08-01');

-- ── Student 6 (Divya Nair) — GH-heavy, weak DSA: 6 coding rows ───────────────
INSERT INTO coding_activity (student_id, problem_id, difficulty, solved_at) VALUES
  (6, 'P060001', 'easy',   '2024-01-25'),
  (6, 'P060002', 'easy',   '2024-03-10'),
  (6, 'P060003', 'medium', '2024-04-20'),
  (6, 'P060004', 'easy',   '2024-05-30'),
  (6, 'P060005', 'easy',   '2024-07-05'),
  (6, 'P060006', 'medium', '2024-08-12');

-- ── Student 7 (Amit Roy) — weak overall: 4 coding rows ───────────────────────
INSERT INTO coding_activity (student_id, problem_id, difficulty, solved_at) VALUES
  (7, 'P070001', 'easy',   '2024-03-01'),
  (7, 'P070002', 'easy',   '2024-04-15'),
  (7, 'P070003', 'easy',   '2024-06-10'),
  (7, 'P070004', 'easy',   '2024-08-05');

-- ── Student 8 (Fatima Khan) — weak overall: 4 coding rows ────────────────────
INSERT INTO coding_activity (student_id, problem_id, difficulty, solved_at) VALUES
  (8, 'P080001', 'easy',   '2024-02-20'),
  (8, 'P080002', 'easy',   '2024-04-10'),
  (8, 'P080003', 'easy',   '2024-06-01'),
  (8, 'P080004', 'easy',   '2024-07-25');

-- ── GitHub activity ───────────────────────────────────────────────────────────

-- Student 1 — strong: 5 rows, high commits
INSERT INTO github_activity (student_id, repo_name, commits, commit_date) VALUES
  (1, 'dsa-solutions',  45, '2024-01-20'),
  (1, 'ml-project',     62, '2024-03-15'),
  (1, 'portfolio',      38, '2024-05-10'),
  (1, 'api-server',     51, '2024-06-28'),
  (1, 'dsa-solutions',  30, '2024-08-05');

-- Student 2 — strong: 4 rows, high commits
INSERT INTO github_activity (student_id, repo_name, commits, commit_date) VALUES
  (2, 'competitive-cp', 58, '2024-02-08'),
  (2, 'web-app',        44, '2024-04-12'),
  (2, 'blog-site',      29, '2024-06-05'),
  (2, 'competitive-cp', 35, '2024-08-01');

-- Student 3 — coder, weak GH: 2 rows, low commits
INSERT INTO github_activity (student_id, repo_name, commits, commit_date) VALUES
  (3, 'leetcode-grind',  8, '2024-03-20'),
  (3, 'leetcode-grind',  5, '2024-07-10');

-- Student 4 — coder, weak GH: 1 row, low commits
INSERT INTO github_activity (student_id, repo_name, commits, commit_date) VALUES
  (4, 'practice-repo',   6, '2024-05-15');

-- Student 5 — GH-heavy: 5 rows, high commits across multiple repos
INSERT INTO github_activity (student_id, repo_name, commits, commit_date) VALUES
  (5, 'open-source-contrib', 95, '2024-01-30'),
  (5, 'devtools',            72, '2024-03-18'),
  (5, 'cli-utils',           60, '2024-05-05'),
  (5, 'react-components',    48, '2024-06-22'),
  (5, 'open-source-contrib', 55, '2024-08-10');

-- Student 6 — GH-heavy: 5 rows, high commits across multiple repos
INSERT INTO github_activity (student_id, repo_name, commits, commit_date) VALUES
  (6, 'fullstack-app',        88, '2024-02-14'),
  (6, 'data-viz',             70, '2024-04-03'),
  (6, 'automation-scripts',   52, '2024-05-25'),
  (6, 'fullstack-app',        40, '2024-07-12'),
  (6, 'data-viz',             35, '2024-08-20');

-- Student 7 — weak overall: 1 row, very low commits
INSERT INTO github_activity (student_id, repo_name, commits, commit_date) VALUES
  (7, 'hello-world', 3, '2024-03-01');

-- Student 8 — zero GitHub activity (no rows)
