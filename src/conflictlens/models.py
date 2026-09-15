from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Answerability(StrEnum):
    SAFE = "SAFE"
    CONDITIONAL = "CONDITIONAL"
    UNSAFE = "UNSAFE"


class AllowedAction(StrEnum):
    ANSWER = "ANSWER"
    ANSWER_WITH_WARNING = "ANSWER_WITH_WARNING"
    ABSTAIN = "ABSTAIN"
    BLOCK_AUTOMATION = "BLOCK_AUTOMATION"


class SourceState(StrEnum):
    APPROVED_DECISION = "APPROVED_DECISION"
    GUIDANCE = "GUIDANCE"
    IMPLEMENTATION = "IMPLEMENTATION"
    DISCUSSION = "DISCUSSION"
    PROPOSAL = "PROPOSAL"
    OPERATIONAL_OBSERVATION = "OPERATIONAL_OBSERVATION"
    OPERATIONAL_REVIEW = "OPERATIONAL_REVIEW"
    SUPERSEDED = "SUPERSEDED"
    UNKNOWN = "UNKNOWN"


class RelationType(StrEnum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    SUPERSEDES = "SUPERSEDES"
    CHALLENGES = "CHALLENGES"


class Evidence(BaseModel):
    source_id: str
    claim_key: str
    claim_value: str
    observed_at: datetime
    source_state: SourceState = SourceState.UNKNOWN
    authority: int = Field(default=1, ge=1, le=5)
    severity: int = Field(default=1, ge=1, le=5)


class Relation(BaseModel):
    from_source_id: str
    to_source_id: str
    type: RelationType
    reason: str = ""


class Conflict(BaseModel):
    claim_key: str
    values: list[str]
    source_ids: list[str]
    conflict_type: str
    max_severity: int
    resolved: bool = False
    resolution_basis: str | None = None


class EvaluationRequest(BaseModel):
    question: str
    evidence: list[Evidence]
    relations: list[Relation] = []


class EvaluationResult(BaseModel):
    decision: Answerability
    allowed_action: AllowedAction
    requires_human_review: bool
    reason_codes: list[str]
    reason: str
    conflicts: list[Conflict]
    evidence: list[Evidence]
