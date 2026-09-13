from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Answerability(StrEnum):
    SAFE = "SAFE"
    CONDITIONAL = "CONDITIONAL"
    UNSAFE = "UNSAFE"


class Evidence(BaseModel):
    source_id: str
    claim_key: str
    claim_value: str
    observed_at: datetime
    authority: int = Field(default=1, ge=1, le=5)
    severity: int = Field(default=1, ge=1, le=5)


class Conflict(BaseModel):
    claim_key: str
    values: list[str]
    source_ids: list[str]
    max_severity: int


class EvaluationRequest(BaseModel):
    question: str
    evidence: list[Evidence]


class EvaluationResult(BaseModel):
    decision: Answerability
    reason: str
    conflicts: list[Conflict]
    evidence: list[Evidence]
