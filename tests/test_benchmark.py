from pathlib import Path

from conflictlens.benchmark import run_benchmark


def test_locked_benchmark() -> None:
    root = Path(__file__).parents[1] / "benchmark"
    results = run_benchmark(root)
    assert len(results) == 10
    failures = [
        f"{r.case_id}: expected {r.expected_decision}/{r.expected_action}, "
        f"got {r.actual_decision}/{r.actual_action}"
        for r in results
        if not r.passed
    ]
    assert not failures, "\n" + "\n".join(failures)
