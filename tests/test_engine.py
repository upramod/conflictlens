from datetime import UTC, datetime

from conflictlens.engine import evaluate
from conflictlens.models import Answerability, EvaluationRequest, Evidence


def evidence(value: str, severity: int = 1) -> Evidence:
    return Evidence(
        source_id=f"source-{value}",
        claim_key="deployment mode",
        claim_value=value,
        observed_at=datetime.now(UTC),
        severity=severity,
    )


def test_safe_when_claims_agree() -> None:
    result = evaluate(EvaluationRequest(question="How do we deploy?", evidence=[evidence("blue")]))
    assert result.decision == Answerability.SAFE


def test_conditional_for_low_severity_conflict() -> None:
    result = evaluate(
        EvaluationRequest(
            question="How do we deploy?",
            evidence=[evidence("blue"), evidence("green")],
        )
    )
    assert result.decision == Answerability.CONDITIONAL


def test_unsafe_for_high_severity_conflict() -> None:
    result = evaluate(
        EvaluationRequest(
            question="Can the agent act?",
            evidence=[evidence("enabled", 5), evidence("disabled", 5)],
        )
    )
    assert result.decision == Answerability.UNSAFE
    assert result.conflicts[0].source_ids == ["source-disabled", "source-enabled"]
