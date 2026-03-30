-- ── Query 1: feature engineering CTE chain ──────────────────────────
-- Run BEFORE adding any new indexes to get the baseline
EXPLAIN ANALYZE
WITH coding_counts AS (
    SELECT student_id, COUNT(*) AS total_problems
    FROM  coding_activity
    GROUP BY student_id
)
SELECT s.id, s.name, cc.total_problems
FROM  students s
LEFT JOIN coding_counts cc ON s.id = cc.student_id;

-- ── Query 2: single-student feature lookup (most frequent API call) ──
EXPLAIN ANALYZE
SELECT s.cgpa, f.*
FROM  students s
JOIN  features  f ON s.id = f.student_id
WHERE s.id = 1;

-- ── Query 3: ranking query with window functions ──────────────────────
EXPLAIN ANALYZE
SELECT s.name, s.branch,
    RANK() OVER (ORDER BY f.total_problems DESC) AS global_rank
FROM  students s
JOIN  features  f ON s.id = f.student_id;