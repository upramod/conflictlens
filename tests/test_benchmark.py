import json
from pathlib import Path

from conflictlens.engine import evaluate
from conflictlens.models import EvaluationRequest


def test_cl001_matches_gold() -> None:
    case_path = Path(__file__).parents[1] / "benchmark" / "CL-001" / "case.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    request = EvaluationRequest(
        question=case["question"],
        evidence=case["evidence"],
        relations=case["relations"],
    )
    result = evaluate(request)
    gold = case["gold"]

    assert result.decision.value == gold["decision"]
    assert result.requires_human_review == gold["requires_human_review"]
    assert result.allowed_action.value == gold["allowed_action"]
    assert set(gold["required_reason_codes"]).issubset(result.reason_codes)
