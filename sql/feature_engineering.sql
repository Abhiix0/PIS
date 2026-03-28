-- =====================================================
-- PIS Feature Engineering Pipeline
-- Run standalone to verify: each CTE is testable alone
-- Final statement: INSERT INTO features
-- =====================================================

WITH

-- ── CTE 1: total problems solved per student ─────────────────────────
coding_counts AS (
    SELECT
        student_id,
        COUNT(*) AS total_problems
    FROM  coding_activity
    GROUP BY student_id
),

-- ── CTE 2: avg difficulty — map labels to 1/2/3 then average ─────────
difficulty_scores AS (
    SELECT
        student_id,
        ROUND(
            AVG(
                CASE difficulty
                    WHEN 'easy'   THEN 1.0
                    WHEN 'medium' THEN 2.0
                    WHEN 'hard'   THEN 3.0
                    ELSE 0.0
                END
            )
        , 2) AS avg_difficulty
    FROM  coding_activity
    GROUP BY student_id
),

-- ── CTE 3: consistency score — active weeks in last 90 days ──────────
-- Logic: extract week number from solved_at, count distinct weeks,
-- divide by 13 (number of weeks in 90 days), cap at 1.0
consistency AS (
    SELECT
        student_id,
        ROUND(
            LEAST(
                COUNT(DISTINCT
                    DATE_TRUNC('week', solved_at)
                )::NUMERIC / 13.0
            , 1.0)
        , 3) AS consistency_score
    FROM  coding_activity
    WHERE solved_at >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY student_id
),

-- ── CTE 4: commit frequency — total commits / active days ────────────
-- NULLIF prevents division-by-zero for student 8 (zero activity)
github_stats AS (
    SELECT
        student_id,
        SUM(commits)                              AS total_commits,
        MIN(commit_date)                            AS first_commit,
        MAX(commit_date)                            AS last_commit,
        ROUND(
            SUM(commits)::NUMERIC /
            NULLIF(
                (CURRENT_DATE - MIN(commit_date))
            , 0)
        , 4) AS commit_frequency
    FROM  github_activity
    GROUP BY student_id
),

-- ── CTE 5: join everything back to the full student list ─────────────
-- LEFT JOINs are critical — student 8 has no github rows
-- COALESCE fills NULLs with safe zero defaults
all_features AS (
    SELECT
        s.id                                                  AS student_id,
        COALESCE(cc.total_problems,    0)                    AS total_problems,
        COALESCE(ds.avg_difficulty,    0.0)                  AS avg_difficulty,
        COALESCE(co.consistency_score, 0.0)                  AS consistency_score,
        COALESCE(gs.commit_frequency,  0.0)                  AS commit_frequency
    FROM       students          s
    LEFT JOIN  coding_counts     cc ON s.id = cc.student_id
    LEFT JOIN  difficulty_scores ds ON s.id = ds.student_id
    LEFT JOIN  consistency       co ON s.id = co.student_id
    LEFT JOIN  github_stats      gs ON s.id = gs.student_id
)

-- ── Final: materialize into the features table ───────────────────────
-- ON CONFLICT updates existing rows (safe to re-run)
INSERT INTO features
    (student_id, total_problems, avg_difficulty,
     consistency_score, commit_frequency, computed_at)
SELECT
    student_id, total_problems, avg_difficulty,
    consistency_score, commit_frequency,
    NOW()
FROM all_features
ON CONFLICT (student_id) DO UPDATE SET
    total_problems    = EXCLUDED.total_problems,
    avg_difficulty    = EXCLUDED.avg_difficulty,
    consistency_score = EXCLUDED.consistency_score,
    commit_frequency  = EXCLUDED.commit_frequency,
    computed_at       = NOW();