-- sql/seed.sql
-- Run AFTER schema.sql
-- Run: psql -U pis_user -d pis_db -f sql/seed.sql

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

-- Coding activity: vary volume and difficulty per archetype
-- Strong students: many hard+medium problems
-- Weak DSA: few easy problems only
INSERT INTO coding_activity (student_id, problem_id, difficulty, solved_at) VALUES
  (1, 'P001', 'hard',   '2024-01-10'),
  (1, 'P002', 'medium', '2024-01-12'),
  (1, 'P003', 'hard',   '2024-01-15'),
  -- ... add 15-20 rows per student with realistic dates
  (7, 'P050', 'easy',   '2024-03-01'),
  (8, 'P051', 'easy',   '2024-03-05');

-- GitHub activity: vary commits and frequency
INSERT INTO github_activity (student_id, repo_name, commits, commit_date) VALUES
  (1, 'portfolio-site',   42, '2024-01-20'),
  (1, 'ml-project',       67, '2024-02-10'),
  (7, 'hello-world',      3,  '2024-03-01');