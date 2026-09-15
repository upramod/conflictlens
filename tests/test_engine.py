from datetime import UTC, datetime

from conflictlens.engine import evaluate
from conflictlens.models import (
    AllowedAction,
    Answerability,
    EvaluationRequest,
    Evidence,
    Relation,
    RelationType,
    SourceState,
)


def evidence(
    value: str,
    *,
    source_id: str | None = None,
    state: SourceState = SourceState.UNKNOWN,
    severity: int = 1,
    key: str = "deployment mode",
) -> Evidence:
    return Evidence(
        source_id=source_id or f"source-{value}",
        claim_key=key,
        claim_value=value,
        observed_at=datetime.now(UTC),
        source_state=state,
        severity=severity,
    )


def test_safe_when_claims_agree() -> None:
    result = evaluate(EvaluationRequest(question="How do we deploy?", evidence=[evidence("blue")]))
    assert result.decision == Answerability.SAFE
    assert result.allowed_action == AllowedAction.ANSWER


def test_conditional_for_untyped_low_severity_conflict() -> None:
    result = evaluate(
        EvaluationRequest(
            question="How do we deploy?",
            evidence=[evidence("blue"), evidence("green")],
        )
    )
    assert result.decision == Answerability.CONDITIONAL
    assert result.allowed_action == AllowedAction.ANSWER_WITH_WARNING


def test_unsafe_for_high_severity_conflict() -> None:
    result = evaluate(
        EvaluationRequest(
            question="Can the agent act?",
            evidence=[evidence("enabled", severity=5), evidence("disabled", severity=5)],
        )
    )
    assert result.decision == Answerability.UNSAFE
    assert result.allowed_action == AllowedAction.BLOCK_AUTOMATION


def test_explicit_supersession_resolves_conflict() -> None:
    result = evaluate(
        EvaluationRequest(
            question="Which API is approved?",
            evidence=[
                evidence("API A", source_id="old", state=SourceState.APPROVED_DECISION, key="account api"),
                evidence("API B", source_id="new", state=SourceState.APPROVED_DECISION, key="account api"),
            ],
            relations=[
                Relation(
                    from_source_id="new",
                    to_source_id="old",
                    type=RelationType.SUPERSEDES,
                    reason="The new decision explicitly replaces the old decision.",
                )
            ],
        )
    )
    assert result.decision == Answerability.SAFE
    assert result.conflicts[0].resolved is True


def test_cl001_is_unsafe_for_structural_reasons() -> None:
    key = "new customer account creation api"
    result = evaluate(
        EvaluationRequest(
            question="Which API should a new service use to create a customer account?",
            evidence=[
                evidence("API A", source_id="architecture", state=SourceState.APPROVED_DECISION, key=key),
                evidence("API B", source_id="wiki", state=SourceState.GUIDANCE, key=key),
                evidence("API A", source_id="production", state=SourceState.IMPLEMENTATION, key=key),
                evidence("API B not production-ready", source_id="discussion", state=SourceState.DISCUSSION, key=key),
                evidence("API B not approved", source_id="readiness", state=SourceState.OPERATIONAL_REVIEW, key=key),
            ],
            relations=[
                Relation(
                    from_source_id="readiness",
                    to_source_id="wiki",
                    type=RelationType.CHALLENGES,
                    reason="The readiness review has not approved API B for production.",
                )
            ],
        )
    )
    assert result.decision == Answerability.UNSAFE
    assert result.requires_human_review is True
    assert result.allowed_action == AllowedAction.BLOCK_AUTOMATION
    assert "NO_CLEAR_SUPERSESSION" in result.reason_codes
    assert "RECENT_OPERATIONAL_CHALLENGE" in result.reason_codes
    assert any(c.conflict_type == "DECISION_VS_GUIDANCE" for c in result.conflicts)
