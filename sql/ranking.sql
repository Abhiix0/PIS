-- Global rank + branch rank using window functions
-- composite_score is a weighted sum of all features
-- weights chosen to reflect placement relevance

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
        -- weighted composite score (raw, pre-ML)
        ROUND(
            (s.cgpa                * 10)  +
            (f.total_problems      *  0.2) +
            (f.avg_difficulty      *  5)  +
            (f.consistency_score   * 20)  +
            (f.commit_frequency    * 15)
        , 2) AS composite_score
    FROM      students s
    JOIN      features  f ON s.id = f.student_id
),

ranked AS (
    SELECT
        *,
        -- global rank across all students
        RANK()       OVER (ORDER BY composite_score DESC)
            AS global_rank,
        -- rank within the student's own branch
        RANK()       OVER (PARTITION BY branch ORDER BY composite_score DESC)
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