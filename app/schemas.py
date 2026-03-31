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
    readiness_score: float
    category:        str
    last_updated:    Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

class RecommendationItem(BaseModel):
    priority:       int
    tier:           str
    area:           str
    action:         str
    why_it_matters: str

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

class InsightResponse(BaseModel):
    student_id:      int
    student_name:    str
    readiness_score: Optional[float]
    category:        Optional[str]
    strengths:       list[StrengthItem]
    weaknesses:      list[WeaknessItem]
    recommendations: list[RecommendationItem]
    top_priority:    str

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