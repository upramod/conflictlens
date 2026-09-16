"""Offline draft validation and recorded-review preflight. Never calls a model."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from conflictlens.research_contract import (  # noqa: E402
    Assessment,
    input_hash,
    read_corpus,
    release_blockers,
    rubric_hash,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "benchmark/vnext/development.json")
    parser.add_argument("--rubric", type=Path, default=ROOT / "benchmark/vnext/RUBRIC.md")
    parser.add_argument("--release-check", action="store_true")
    parser.add_argument("--schema", action="store_true", help="Print the assessment JSON schema")
    args = parser.parse_args()
    if args.schema:
        print(json.dumps(Assessment.model_json_schema(), indent=2))
        return 0
    try:
        corpus = read_corpus(args.corpus)
        rubric = args.rubric.read_text(encoding="utf-8")
        blockers = release_blockers(corpus, rubric)
    except (OSError, ValueError, TypeError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"revision={corpus.revision} status={corpus.status}")
    print(f"cases={len(corpus.cases)} parents={len({c.parent_id for c in corpus.cases})}")
    print(f"unique_inputs={len({input_hash(c.input) for c in corpus.cases})}")
    print(f"splits={dict(Counter(c.split for c in corpus.cases))}")
    print(f"human_review_records={sum(len(c.reviews) for c in corpus.cases)}")
    print(f"rubric_sha256={rubric_hash(rubric)}")
    print("contract_validation=PASS (format and references, not semantic correctness)")
    print(f"evaluation_release={'BLOCKED' if blockers else 'RECORDED_PREREQUISITES_MET'}")
    for blocker in blockers:
        print(f"  - {blocker}")
    return 2 if args.release_check and blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
