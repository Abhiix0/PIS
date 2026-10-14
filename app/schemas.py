from pydantic   import BaseModel, Field, EmailStr, field_validator, ConfigDict
from typing     import Optional
from datetime   import datetime

# ── Request schemas (what the client sends IN) ────────────────────────

class StudentCreate(BaseModel):
    name:              str   = Field(..., min_length=2, max_length=100)
    email:             EmailStr
    cgpa:              float = Field(..., ge=0.0, le=10.0)
    branch:            str   = Field(..., min_length=2, max_length=50)
    github_username:   Optional[str] = None
    leetcode_username: Optional[str] = None

    @field_validator('branch')
    @classmethod
    def branch_uppercase(cls, v: str) -> str:
        return v.upper().strip()

# ── Response schemas (what the API sends OUT) ─────────────────────────

class StudentResponse(BaseModel):
    id:                int
    name:              str
    email:             str
    cgpa:              float
    branch:            str
    github_username:   Optional[str] = None
    leetcode_username: Optional[str] = None
    created_at:        datetime

    model_config = ConfigDict(from_attributes=True)

class FeatureResponse(BaseModel):
    student_id:        int
    total_problems:    int
    avg_difficulty:    float
    consistency_score: float
    commit_frequency:  float
    computed_at:       Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

class PredictionResponse(BaseModel):
    student_id:      int
    assessment_type: str = "ml_readiness_proxy"  # or "insufficient_evidence" (then no score)
    readiness_score: Optional[float] = None
    category:        Optional[str] = None
    reason:          Optional[str] = None
    model_version:   Optional[str] = None
    last_updated:    Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

class RecommendationItem(BaseModel):
    priority:       int
    tier:           str
    area:           str
    action:         str
    why_it_matters: str
    basis:          Optional[str] = None
    limitation:     Optional[str] = None

class WeaknessItem(BaseModel):
    feature:        str
    label:          str
    message:        str
    raw_value:      float
    importance:     float

class StrengthItem(BaseModel):
    feature: str
    label:   str
    message: str

class CompositeInsight(BaseModel):
    pattern: str
    message: str
    action:  str


class CompanyTier(BaseModel):
    tier:     str
    examples: list[str]
    focus:    str


class InsightResponse(BaseModel):
    student_id:          int
    student_name:        str
    readiness_score:     Optional[float]
    category:            Optional[str]
    company_tier:        Optional[CompanyTier] = None
    score_delta_7d:      Optional[float] = None
    score_trend:         Optional[str]   = None
    features_age_hours:  Optional[float] = None
    features_stale:      bool            = False
    strengths:           list[StrengthItem]
    weaknesses:          list[WeaknessItem]
    composite_insights:  list[CompositeInsight] = []
    recommendations:     list[RecommendationItem]
    top_priority:        str

class RankingItem(BaseModel):
    global_rank:     int
    branch_rank:     int
    name:            str
    branch:          str
    cgpa:            float
    total_problems:  int
    composite_score: float
    percentile:      float

class IngestResponse(BaseModel):
    student_id:  int
    inserted:    int
    skipped:     int
    message:     str
    data_source: str = "synthetic"


class PipelineStep(BaseModel):
    step:             str
    status:           str  # "success" or "error"
    duration_ms:      float
    data_source:      Optional[str] = None
    records_inserted: Optional[int] = None
    readiness_score:  Optional[float] = None
    category:         Optional[str] = None
    weaknesses_found: Optional[int] = None
    error:            Optional[str] = None


class PipelineResponse(BaseModel):
    student_id:          int
    student_name:        str
    readiness_score:     Optional[float]
    category:            Optional[str]
    company_tier:        Optional[CompanyTier] = None
    score_delta_7d:      Optional[float] = None
    score_trend:         Optional[str]   = None
    features_age_hours:  Optional[float] = None
    features_stale:      bool            = False
    strengths:           list[StrengthItem]
    weaknesses:          list[WeaknessItem]
    composite_insights:  list[CompositeInsight] = []
    recommendations:     list[RecommendationItem]
    top_priority:        str
    pipeline_steps:      list[PipelineStep]
    total_duration_ms:   float
    ran_at:              str


class StudentListItem(BaseModel):
    id:              int
    name:            str
    email:           str
    branch:          str
    cgpa:            float
    category:        Optional[str] = None
    readiness_score: Optional[float] = None
    has_prediction:  bool = False


class StudentStatus(BaseModel):
    student_id:           int
    name:                 str
    branch:               str
    cgpa:                 float
    github_username:      Optional[str] = None
    leetcode_username:    Optional[str] = None
    features_computed:    bool
    features_computed_at: Optional[datetime] = None
    prediction_exists:    bool
    readiness_score:      Optional[float] = None
    category:             Optional[str] = None
    prediction_updated:   Optional[datetime] = None
    pipeline_stage:       str  # "no_data"|"features_computed"|"predicted"|"complete"


class BatchPipelineRequest(BaseModel):
    student_ids: list[int] = Field(..., min_length=1, max_length=20)


class StudentUpdate(BaseModel):
    github_username:   Optional[str]   = None
    leetcode_username: Optional[str]   = None
    cgpa:              Optional[float] = Field(None, ge=0.0, le=10.0)


class PredictionHistoryItem(BaseModel):
    readiness_score: float
    category:        str
    recorded_at:     datetime
