"""Contract checks, not evidence of model quality or adjudicated case accuracy."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from conflictlens.research_contract import (
    Assessment,
    Corpus,
    DevelopmentCase,
    TaskInput,
    check_integrity,
    input_hash,
    model_payload,
    parse_assessment,
    read_corpus,
    release_blockers,
    rubric_hash,
    strict_json,
    validate_assessment,
)

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "benchmark/vnext/development.json"
RUBRIC = ROOT / "benchmark/vnext/RUBRIC.md"


@pytest.fixture
def corpus():
    return read_corpus(PACK)


@pytest.fixture
def case(corpus):
    return corpus.cases[0]


def test_all_candidates_have_valid_format_and_real_quotes(corpus):
    assert len(corpus.cases) == 14
    assert len({case.parent_id for case in corpus.cases}) == 7
    assert len({input_hash(case.input) for case in corpus.cases}) == 14
    assert corpus.status == "draft"
    assert all(case.split == "development" and not case.reviews for case in corpus.cases)
    for case in corpus.cases:
        validate_assessment(case.input, case.candidate)


@pytest.mark.parametrize("permission", ["REQUIRES_APPROVAL", "PROHIBITED", "PERMITTED"])
def test_answerable_does_not_mean_permission_granted(case, permission):
    data = case.candidate.model_dump(mode="json")
    data["action_permission"] = permission
    assessment = parse_assessment(json.dumps(data), case.input)
    assert assessment.answerability == "ANSWERABLE"
    assert assessment.action_permission == permission


def test_no_forced_mapping_from_conflict_to_answerability(corpus):
    case = next(c for c in corpus.cases if c.case_id == "VN-SUP-02")
    data = case.candidate.model_dump(mode="json")
    data["answerability"] = "ANSWERABLE"
    assessment = parse_assessment(json.dumps(data), case.input)
    assert assessment.conflict == "UNRESOLVED"


@pytest.mark.parametrize("body", [
    '{"answerability":"ANSWERABLE","answerability":"INSUFFICIENT"}',
    '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}',
])
def test_nonstandard_or_duplicate_json_rejected(body):
    with pytest.raises(ValueError):
        strict_json(body)


@pytest.mark.parametrize("wrapper", ["prefix {body}", "```json\n{body}\n```", "{body}\nUNSAFE"])
def test_prose_is_not_parsed_as_structured_result(case, wrapper):
    text = wrapper.format(body=case.candidate.model_dump_json())
    with pytest.raises(ValueError):
        parse_assessment(text, case.input)


def test_explanation_label_words_cannot_override_enum(case):
    data = case.candidate.model_dump(mode="json")
    data["answer"] = "SAFE, CONDITIONAL and UNSAFE are legacy label words."
    assessment = parse_assessment(json.dumps(data), case.input)
    assert assessment.answerability == "ANSWERABLE"
    assert assessment.action_permission == "REQUIRES_APPROVAL"


@pytest.mark.parametrize("field,value", [
    ("answerability", "SAFE"), ("answerability", "answerable"),
    ("conflict", "no"), ("action_permission", "ANSWER"),
    ("answer", 42), ("answer", "   "),
])
def test_invalid_enum_and_text_types_rejected(case, field, value):
    data = case.candidate.model_dump(mode="json")
    data[field] = value
    with pytest.raises(ValidationError):
        parse_assessment(json.dumps(data), case.input)


def test_extra_output_fields_rejected(case):
    data = case.candidate.model_dump(mode="json")
    data["approved"] = True
    with pytest.raises(ValidationError):
        parse_assessment(json.dumps(data), case.input)


@pytest.mark.parametrize("source,quote", [("unknown", "text"), ("s1", "fabricated evidence")])
def test_invented_citations_rejected(case, source, quote):
    data = case.candidate.model_dump(mode="json")
    data["basis"]["answerability"]["citations"] = [{"source_id": source, "quote": quote}]
    with pytest.raises(ValueError):
        parse_assessment(json.dumps(data), case.input)


def test_duplicate_citations_rejected(case):
    data = case.candidate.model_dump(mode="json")
    citations = data["basis"]["answerability"]["citations"]
    citations.append(copy.deepcopy(citations[0]))
    with pytest.raises(ValueError, match="duplicate citation"):
        parse_assessment(json.dumps(data), case.input)


@pytest.mark.parametrize("axis", ["answerability", "action_permission"])
def test_determinate_decision_needs_citation(case, axis):
    data = case.candidate.model_dump(mode="json")
    data["basis"][axis]["citations"] = []
    with pytest.raises(ValueError, match="needs"):
        parse_assessment(json.dumps(data), case.input)


def test_not_requested_cannot_mask_real_action(case):
    data = case.candidate.model_dump(mode="json")
    data["action_permission"] = "NOT_REQUESTED"
    with pytest.raises(ValueError, match="NOT_REQUESTED"):
        parse_assessment(json.dumps(data), case.input)


def test_fact_only_task_cannot_receive_permission(corpus):
    case = next(c for c in corpus.cases if c.case_id == "VN-SUP-01")
    data = case.candidate.model_dump(mode="json")
    data["action_permission"] = "PROHIBITED"
    with pytest.raises(ValueError, match="NOT_REQUESTED"):
        parse_assessment(json.dumps(data), case.input)


def test_missing_evidence_can_be_insufficient(corpus):
    case = next(c for c in corpus.cases if c.case_id == "VN-MISS-02")
    data = case.model_dump(mode="json")
    data["input"]["sources"] = []
    for basis in data["candidate"]["basis"].values():
        basis["citations"] = []
    result = DevelopmentCase.model_validate(data)
    assert result.candidate.answerability == "INSUFFICIENT"


@pytest.mark.parametrize("mutation", ["duplicates", "future", "naive"])
def test_bad_source_metadata_rejected(case, mutation):
    data = case.input.model_dump(mode="json")
    if mutation == "duplicates":
        data["sources"].append(copy.deepcopy(data["sources"][0]))
    elif mutation == "future":
        data["sources"][0]["issued_at"] = "2027-01-01T00:00:00Z"
    else:
        data["as_of"] = "2026-09-16T00:00:00"
    with pytest.raises(ValidationError):
        TaskInput.model_validate(data)


def test_no_candidate_metadata_leaks_into_model_payload(case):
    rubric = RUBRIC.read_text(encoding="utf-8")
    payload = model_payload(case, rubric)
    assert set(payload) == {"rubric", "task"}
    assert set(payload["task"]) == {"question", "as_of", "proposed_action", "sources"}
    assert payload["rubric"] == rubric
    assert "candidate" not in payload and "reviews" not in payload
    changed = case.model_copy(update={"case_id": "OTHER", "parent_id": "OTHER"})
    assert model_payload(changed, rubric) == payload


def test_raw_source_text_is_retained(case):
    payload = model_payload(case, "rubric")
    assert payload["task"]["sources"][0]["text"] == case.input.sources[0].text


def test_exact_duplicate_task_rejected(corpus):
    duplicate = corpus.cases[0].model_copy(update={"case_id": "DUPLICATE"})
    changed = corpus.model_copy(update={"cases": [*corpus.cases, duplicate]})
    with pytest.raises(ValueError, match="duplicate task"):
        check_integrity(changed)


def test_parent_split_leakage_rejected(corpus):
    data = corpus.model_dump(mode="json")
    data["cases"][1]["split"] = "held_out"
    changed = Corpus.model_validate(data)
    with pytest.raises(ValueError, match="parent scenario"):
        check_integrity(changed)


def test_reordered_input_cannot_be_moved_to_another_split(corpus):
    data = corpus.model_dump(mode="json")
    twin = copy.deepcopy(data["cases"][1])
    twin["case_id"], twin["parent_id"], twin["split"] = "TWIN", "TWIN", "held_out"
    twin["input"]["sources"].reverse()
    data["cases"].append(twin)
    with pytest.raises(ValueError, match="reordered"):
        check_integrity(Corpus.model_validate(data))


def test_hash_changes_with_input_not_candidate(case):
    data = case.input.model_dump(mode="json")
    data["question"] += " Explain the time scope."
    assert input_hash(TaskInput.model_validate(data)) != input_hash(case.input)
    assert rubric_hash("a\r\nb") == rubric_hash("a\nb")
    assert rubric_hash("a") != rubric_hash("b")


def reviewed_fixture(corpus, rubric):
    """Fabricated test records only. Never written to the development corpus."""
    data = corpus.model_dump(mode="json")
    data["status"] = "reviewed"
    data["cases"] = [data["cases"][-1]]
    target = data["cases"][0]
    target["split"] = "held_out"
    for reviewer in ["test-person-1", "test-person-2"]:
        target["reviews"].append({
            "reviewer_id": reviewer, "is_human": True, "independent_of_case_author": True,
            "blinded_to_candidate_and_outputs": True,
            "input_sha256": input_hash(TaskInput.model_validate(target["input"])),
            "rubric_sha256": rubric_hash(rubric), "reviewed_at": "2026-09-16T00:00:00Z",
            "assessment": target["candidate"],
        })
    return data


def test_actual_draft_cannot_pass_release(corpus):
    blockers = release_blockers(corpus, RUBRIC.read_text(encoding="utf-8"))
    assert "corpus is draft, not reviewed" in blockers
    assert "no held-out parent scenarios recorded" in blockers
    assert any("two separate human annotations" in b for b in blockers)


def test_recorded_prerequisites_can_be_checked_without_certifying_truth(corpus):
    rubric = RUBRIC.read_text(encoding="utf-8")
    assert not release_blockers(Corpus.model_validate(reviewed_fixture(corpus, rubric)), rubric)


@pytest.mark.parametrize("mutation,fragment", [
    ("hash", "different input or rubric"), ("rubric", "different input or rubric"),
    ("ai", "human/blinded"), ("unblinded", "human/blinded"),
    ("same_person", "duplicate reviewer"), ("no_independence", "independent-of-author"),
    ("disagreement", "adjudication"), ("pilot", "prior pilot"),
])
def test_release_prerequisites_cannot_be_skipped(corpus, mutation, fragment):
    rubric = RUBRIC.read_text(encoding="utf-8")
    data = reviewed_fixture(corpus, rubric)
    case = data["cases"][0]
    review = case["reviews"][0]
    if mutation == "hash":
        review["input_sha256"] = "0" * 64
    elif mutation == "rubric":
        review["rubric_sha256"] = "0" * 64
    elif mutation == "ai":
        review["is_human"] = False
    elif mutation == "unblinded":
        review["blinded_to_candidate_and_outputs"] = False
    elif mutation == "same_person":
        review["reviewer_id"] = case["reviews"][1]["reviewer_id"]
    elif mutation == "no_independence":
        for item in case["reviews"]:
            item["independent_of_case_author"] = False
    elif mutation == "disagreement":
        review["assessment"] = copy.deepcopy(review["assessment"])
        review["assessment"]["action_permission"] = "UNDETERMINED"
    else:
        case["prior_experiment_parent"] = "CL-010"
    blockers = release_blockers(Corpus.model_validate(data), rubric)
    assert any(fragment in b for b in blockers)


def test_schema_forbids_unknown_properties():
    schema = Assessment.model_json_schema()
    assert schema["additionalProperties"] is False
    assert {"answerability", "conflict", "action_permission"} <= set(schema["required"])


@pytest.mark.parametrize("release,expected", [(False, 0), (True, 2)])
def test_cli_distinguishes_valid_draft_from_release_ready(release, expected):
    command = [sys.executable, str(ROOT / "tools/validate_vnext.py")]
    if release:
        command.append("--release-check")
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == expected, result.stderr
    assert "contract_validation=PASS" in result.stdout
    assert "evaluation_release=BLOCKED" in result.stdout


def test_review_export_contains_inputs_not_candidate_labels(tmp_path, corpus):
    out = tmp_path / "review"
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/prepare_vnext_review.py"), "--output-dir", str(out)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    exported = [json.loads(line) for line in (out / "inputs.jsonl").read_text().splitlines()]
    assert len(exported) == len(corpus.cases)
    for item in exported:
        assert set(item) == {"case_id", "input_sha256", "task"}
        assert set(item["task"]) == {"as_of", "question", "proposed_action", "sources"}
    packet = (out / "CASES.md").read_text()
    assert "answerability: ____________________" in packet
    assert corpus.cases[0].candidate.answer not in packet
    again = subprocess.run(
        [sys.executable, str(ROOT / "tools/prepare_vnext_review.py"), "--output-dir", str(out)],
        capture_output=True, text=True, check=False,
    )
    assert again.returncode != 0
