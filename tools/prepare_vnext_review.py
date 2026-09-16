"""Export an input-only reviewer packet. No candidates, prior outputs, or API calls."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from conflictlens.research_contract import (
    input_hash,
    model_payload,
    read_corpus,
    rubric_hash,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "benchmark/vnext/development.json")
    parser.add_argument("--rubric", type=Path, default=ROOT / "benchmark/vnext/RUBRIC.md")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    corpus = read_corpus(args.corpus)
    rubric = args.rubric.read_text(encoding="utf-8")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "RUBRIC.md").write_text(rubric, encoding="utf-8")
    inputs = []
    packet = [
        "# Development-case review packet", "",
        "All cases are synthetic development examples, not held-out test data.",
        "Candidate labels and model outputs are omitted. This export does not prove blinding.",
        "Read RUBRIC.md, then annotate each axis before consulting any proposed labels.",
        "Record your actual reviewer identity, role, review time, and rubric hash separately.",
        "Do not assert independent or blind review unless that describes your review process.",
        f"Rubric SHA-256: `{rubric_hash(rubric)}`", "",
    ]
    for case in corpus.cases:
        payload = model_payload(case, rubric)
        inputs.append({"case_id": case.case_id, "input_sha256": input_hash(case.input),
                       "task": payload["task"]})
        packet += [f"## {case.case_id}", "", case.input.question, "",
                   f"As of: {case.input.as_of.isoformat()}", "",
                   "Proposed action:", "```json",
                   json.dumps(payload["task"]["proposed_action"], indent=2), "```", ""]
        for source in case.input.sources:
            packet += [f"### {source.source_id}", "",
                       f"Issued: {source.issued_at.isoformat()}", "", source.text, ""]
        packet += ["### Your annotation", "",
                   "answerability: ____________________",
                   "conflict: ____________________",
                   "action_permission: ____________________", "",
                   "Answer, axis-specific rationale, source IDs and exact supporting quotes:",
                   "", "____________________________________________________________", ""]
    (args.output_dir / "CASES.md").write_text("\n".join(packet), encoding="utf-8")
    (args.output_dir / "inputs.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in inputs), encoding="utf-8"
    )
    print(f"Exported {len(inputs)} unannotated review inputs to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
