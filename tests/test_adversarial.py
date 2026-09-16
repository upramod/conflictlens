import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from conflictlens.engine import evaluate
from conflictlens.models import EvaluationRequest

ROOT = Path(__file__).parents[1]
CASES = ROOT / "benchmark" / "adversarial" / "cases"


def test_engine_v0_adversarial_corpus() -> None:
    subprocess.run([sys.executable, str(ROOT / "tools" / "generate_adversarial.py")], check=True)
    paths = sorted(CASES.glob("*.json"))
    assert len(paths) == 150

    failures = []
    family_counts = Counter()
    family_failures = Counter()
    for path in paths:
        case = json.loads(path.read_text())
        result = evaluate(EvaluationRequest(
            question=case["question"],
            evidence=case["evidence"],
            relations=case.get("relations", []),
        ))
        gold = case["gold"]
        family = case["variant_family"]
        family_counts[family] += 1
        passed = (
            result.decision.value == gold["decision"]
            and result.allowed_action.value == gold["allowed_action"]
            and result.requires_human_review == gold["requires_human_review"]
        )
        if not passed:
            family_failures[family] += 1
            failures.append(
                f'{case["case_id"]}: expected {gold["decision"]}/{gold["allowed_action"]}, '
                f'got {result.decision.value}/{result.allowed_action.value}'
            )

    summary = ", ".join(
        f"{family}={family_counts[family]-family_failures[family]}/{family_counts[family]}"
        for family in sorted(family_counts)
    )
    assert not failures, f"family results: {summary}\n" + "\n".join(failures)
