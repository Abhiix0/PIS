-- Phase 4: deterministic rules-v1 assessments. Additive and backward compatible: old rows keep their type and get result NULL.
-- 'rules_assessment' is a result with per-dimension evidence states and no score (readiness_score stays NULL).
ALTER TABLE assessments DROP CONSTRAINT assessments_assessment_type_check;
ALTER TABLE assessments ADD CONSTRAINT assessments_assessment_type_check
    CHECK (assessment_type IN ('insufficient_evidence','ml_readiness_proxy','rules_assessment'));
ALTER TABLE assessments ADD COLUMN result JSONB;  -- immutable like the rest of the row (trigger in 007)
