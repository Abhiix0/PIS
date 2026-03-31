-- Global rank + branch rank using window functions
-- composite_score = ML readiness_score (0–100, calibrated by Random Forest)
-- Ranking by the model's output is coherent: all features are already
-- scaled and weighted by the trained regressor, not by hand-tuned constants.

WITH scored AS (
    SELECT
        s.id,
        s.name,
        s.branch,
        s.cgpa,
        f.total_problems,
        f.avg_difficulty,
        f.consistency_score,
        f.commit_frequency,
        p.readiness_score AS composite_score
    FROM      students    s
    JOIN      features    f ON s.id = f.student_id
    JOIN      predictions p ON s.id = p.student_id
),

ranked AS (
    SELECT
        *,
        -- global rank across all students
        RANK() OVER (ORDER BY composite_score DESC)
            AS global_rank,
        -- rank within the student's own branch
        RANK() OVER (PARTITION BY branch ORDER BY composite_score DESC)
            AS branch_rank,
        -- percentile: what % of students this student outperforms
        ROUND(
            100.0 * (1 - (
                RANK() OVER (ORDER BY composite_score DESC) - 1
            )::NUMERIC / COUNT(*) OVER ())
        , 1) AS percentile
    FROM scored
)

SELECT
    global_rank,
    branch_rank,
    name,
    branch,
    cgpa,
    total_problems,
    composite_score,
    percentile
FROM  ranked
ORDER BY global_rank;
