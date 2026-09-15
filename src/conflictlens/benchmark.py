import json
from dataclasses import dataclass
from pathlib import Path

from .engine import evaluate
from .models import EvaluationRequest


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    expected_decision: str
    actual_decision: str
    expected_action: str
    actual_action: str
    passed: bool


def run_case(path: Path) -> CaseResult:
    payload = json.loads(path.read_text())
    request = EvaluationRequest(
        question=payload["question"],
        evidence=payload["evidence"],
        relations=payload.get("relations", []),
    )
    result = evaluate(request)
    gold = payload["gold"]
    required = set(gold.get("required_reason_codes", []))
    passed = (
        result.decision.value == gold["decision"]
        and result.allowed_action.value == gold["allowed_action"]
        and result.requires_human_review == gold["requires_human_review"]
        and required.issubset(set(result.reason_codes))
    )
    return CaseResult(
        case_id=payload["case_id"],
        expected_decision=gold["decision"],
        actual_decision=result.decision.value,
        expected_action=gold["allowed_action"],
        actual_action=result.allowed_action.value,
        passed=passed,
    )


def run_benchmark(root: Path) -> list[CaseResult]:
    return [run_case(path) for path in sorted(root.glob("CL-*/case.json"))]
