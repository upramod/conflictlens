import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from conflictlens.engine import evaluate
from conflictlens.models import EvaluationRequest

ROOT = Path(__file__).parents[1]
CASES = ROOT / "benchmark" / "adversarial" / "cases"
EXPECTED_FAILURES = {
    "CL-002-M-01",
    "CL-005-R-01",
    "CL-007-R-01",
    "CL-009-R-01",
    "CL-010-M-01",
}
EXPECTED_FAMILY_PASSES = {
    "A": (10, 10),
    "D": (20, 20),
    "M": (8, 10),
    "N": (20, 20),
    "O": (30, 30),
    "P": (30, 30),
    "R": (7, 10),
    "T": (20, 20),
}


def test_engine_v0_adversarial_baseline_is_frozen() -> None:
    subprocess.run([sys.executable, str(ROOT / "tools" / "generate_adversarial.py")], check=True)
    paths = sorted(CASES.glob("*.json"))
    assert len(paths) == 150

    failures = set()
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
            failures.add(case["case_id"])

    observed = {
        family: (family_counts[family] - family_failures[family], family_counts[family])
        for family in sorted(family_counts)
    }
    assert failures == EXPECTED_FAILURES
    assert observed == EXPECTED_FAMILY_PASSES
    assert sum(passed for passed, _ in observed.values()) == 145
