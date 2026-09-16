"""Draft vNext research contracts. No inference, model calls, or tool execution.

Validation checks syntax, references, and recorded review prerequisites. It does
not establish that a judgment is correct or that a reviewer is independent.
The v0 engine, labels, collector, and scorer are intentionally not imported.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    model_validator,
)

REVISION = "0.3.0-draft.1"
Text = Annotated[str, StringConstraints(strict=True, min_length=1, pattern=r"\S")]
Digest = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]
Answerability = Literal["ANSWERABLE", "QUALIFIED", "INSUFFICIENT"]
ConflictState = Literal["NONE", "RESOLVED", "UNRESOLVED", "UNKNOWN"]
ActionPermission = Literal[
    "NOT_REQUESTED", "PERMITTED", "REQUIRES_APPROVAL", "PROHIBITED", "UNDETERMINED"
]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(Record):
    source_id: Text
    issued_at: AwareDatetime
    text: Text


class ProposedAction(Record):
    actor: Text
    operation: Text
    resource: Text
    environment: Text
    parameters: Text


class TaskInput(Record):
    as_of: AwareDatetime
    question: Text
    proposed_action: ProposedAction | None
    sources: list[Source]

    @model_validator(mode="after")
    def check_sources(self) -> Self:
        ids = [source.source_id for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("source IDs must be unique within a task")
        if any(source.issued_at > self.as_of for source in self.sources):
            raise ValueError("source issued_at is after the task as_of")
        return self


class Citation(Record):
    source_id: Text
    quote: Text


class Basis(Record):
    rationale: Text
    citations: list[Citation]


class AxisBasis(Record):
    answerability: Basis
    conflict: Basis
    action_permission: Basis


class Assessment(Record):
    """Separate answers from permissions; a coherent refusal is ANSWERABLE."""

    answerability: Answerability
    conflict: ConflictState
    action_permission: ActionPermission
    answer: Text
    basis: AxisBasis


class HumanReview(Record):
    reviewer_id: Text
    is_human: StrictBool
    independent_of_case_author: StrictBool
    blinded_to_candidate_and_outputs: StrictBool
    input_sha256: Digest
    rubric_sha256: Digest
    reviewed_at: AwareDatetime
    assessment: Assessment


class DevelopmentCase(Record):
    case_id: Text
    parent_id: Text
    split: Literal["development", "held_out"]
    prior_experiment_parent: Text | None
    input: TaskInput
    candidate: Assessment
    reviews: list[HumanReview] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_assessments(self) -> Self:
        validate_assessment(self.input, self.candidate)
        for review in self.reviews:
            validate_assessment(self.input, review.assessment)
        return self


class Corpus(Record):
    revision: Literal["0.3.0-draft.1"]
    status: Literal["draft", "reviewed"]
    ai_use_disclosure: Text
    cases: list[DevelopmentCase] = Field(min_length=1)


def validate_assessment(task: TaskInput, assessment: Assessment) -> None:
    """Check observable constraints, not the semantic truth of the assessment."""
    not_requested = assessment.action_permission == "NOT_REQUESTED"
    if not_requested != (task.proposed_action is None):
        raise ValueError("NOT_REQUESTED must match the absence of a proposed action")
    sources = {source.source_id: source.text for source in task.sources}
    for axis in ("answerability", "conflict", "action_permission"):
        basis = getattr(assessment.basis, axis)
        seen = set()
        for citation in basis.citations:
            if citation.source_id not in sources:
                raise ValueError(f"{axis}: unknown citation source {citation.source_id}")
            if citation.quote not in sources[citation.source_id]:
                raise ValueError(f"{axis}: citation quote not present in source text")
            pair = (citation.source_id, citation.quote)
            if pair in seen:
                raise ValueError(f"{axis}: duplicate citation")
            seen.add(pair)
    if assessment.answerability != "INSUFFICIENT" and not assessment.basis.answerability.citations:
        raise ValueError("a supported answer needs an answerability citation")
    if assessment.conflict in {"RESOLVED", "UNRESOLVED"}:
        ids = {c.source_id for c in assessment.basis.conflict.citations}
        if len(ids) < 2:
            raise ValueError("a multi-source disagreement needs citations to at least two sources")
    if assessment.action_permission in {"PERMITTED", "REQUIRES_APPROVAL", "PROHIBITED"}:
        if not assessment.basis.action_permission.citations:
            raise ValueError("a permission decision needs source evidence")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonstandard JSON constant: {value}")


def strict_json(text: str) -> Any:
    """No prose scanning, Markdown stripping, duplicate keys, or NaN/Infinity."""
    return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)


def parse_assessment(text: str, task: TaskInput) -> Assessment:
    assessment = Assessment.model_validate(strict_json(text))
    validate_assessment(task, assessment)
    return assessment


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rubric_hash(text: str) -> str:
    """Use LF so a Windows checkout does not invalidate a text-identical rubric."""
    return sha256_text(text.replace("\r\n", "\n"))


def input_hash(task: TaskInput, *, ignore_source_order: bool = False) -> str:
    data = task.model_dump(mode="json")
    if ignore_source_order:
        data["sources"] = sorted(data["sources"], key=lambda item: item["source_id"])
    return sha256_text(canonical_json(data))


def model_payload(case: DevelopmentCase, rubric: str) -> dict[str, Any]:
    """Whitelist identical task/rubric inputs; never pass candidates or reviews."""
    return {"rubric": rubric, "task": case.input.model_dump(mode="json")}


def read_corpus(path: Path) -> Corpus:
    corpus = Corpus.model_validate(strict_json(path.read_text(encoding="utf-8")))
    check_integrity(corpus)
    return corpus


def check_integrity(corpus: Corpus) -> None:
    ids = [case.case_id for case in corpus.cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case IDs")
    groups: dict[str, set[str]] = defaultdict(set)
    inputs: dict[str, str] = {}
    orderless: dict[str, tuple[str, str]] = {}
    for case in corpus.cases:
        groups[case.parent_id].add(case.split)
        digest = input_hash(case.input)
        if digest in inputs:
            raise ValueError(f"duplicate task input: {inputs[digest]} and {case.case_id}")
        inputs[digest] = case.case_id
        unordered_digest = input_hash(case.input, ignore_source_order=True)
        previous = orderless.get(unordered_digest)
        if previous and previous != (case.parent_id, case.split):
            raise ValueError("reordered task crosses parent or split boundary")
        orderless[unordered_digest] = (case.parent_id, case.split)
    if any(len(splits) > 1 for splits in groups.values()):
        raise ValueError("parent scenario occurs in both development and held_out")


def release_blockers(corpus: Corpus, rubric: str) -> list[str]:
    """Prerequisites for a later evaluation freeze, not proof of review quality.

    These are recorded human attestations. The program cannot authenticate people,
    check whether they were blinded, or certify that held-out tasks were not seen.
    """
    check_integrity(corpus)
    blockers: list[str] = []
    if corpus.status != "reviewed":
        blockers.append("corpus is draft, not reviewed")
    if not any(case.split == "held_out" for case in corpus.cases):
        blockers.append("no held-out parent scenarios recorded")
    digest = rubric_hash(rubric)
    for case in corpus.cases:
        if case.split == "held_out" and case.prior_experiment_parent is not None:
            blockers.append(f"{case.case_id}: a prior pilot parent is not held-out")
        reviewer_ids = [review.reviewer_id for review in case.reviews]
        if len(reviewer_ids) != len(set(reviewer_ids)):
            blockers.append(f"{case.case_id}: duplicate reviewer identity")
        if len(set(reviewer_ids)) < 2:
            blockers.append(f"{case.case_id}: two separate human annotations are required")
        if not any(review.independent_of_case_author for review in case.reviews):
            blockers.append(f"{case.case_id}: no independent-of-author reviewer recorded")
        target = case.candidate.model_dump(include={"answerability", "conflict", "action_permission"})
        for review in case.reviews:
            if not review.is_human or not review.blinded_to_candidate_and_outputs:
                blockers.append(f"{case.case_id}: review lacks human/blinded attestations")
            if review.input_sha256 != input_hash(case.input) or review.rubric_sha256 != digest:
                blockers.append(f"{case.case_id}: review is bound to different input or rubric")
            labels = review.assessment.model_dump(
                include={"answerability", "conflict", "action_permission"}
            )
            if labels != target:
                blockers.append(f"{case.case_id}: annotation disagreement needs adjudication")
    return blockers
