from collections import defaultdict

from .models import (
    AllowedAction,
    Answerability,
    Conflict,
    EvaluationRequest,
    EvaluationResult,
    RelationType,
    SourceState,
)


def _norm(value: str) -> str:
    return " ".join(value.casefold().split())


def _conflict_type(items) -> str:
    states = {item.source_state for item in items}
    if SourceState.APPROVED_DECISION in states and SourceState.GUIDANCE in states:
        return "DECISION_VS_GUIDANCE"
    if SourceState.APPROVED_DECISION in states and SourceState.IMPLEMENTATION in states:
        return "DECISION_VS_IMPLEMENTATION"
    if SourceState.PROPOSAL in states and SourceState.APPROVED_DECISION in states:
        return "PROPOSAL_VS_DECISION"
    return "DIRECT_CONTRADICTION"


def evaluate(request: EvaluationRequest) -> EvaluationResult:
    groups = defaultdict(list)
    for item in request.evidence:
        groups[_norm(item.claim_key)].append(item)

    superseded_pairs = {
        (relation.from_source_id, relation.to_source_id)
        for relation in request.relations
        if relation.type == RelationType.SUPERSEDES
    }
    challenged_sources = {
        relation.to_source_id
        for relation in request.relations
        if relation.type == RelationType.CHALLENGES
    }

    conflicts: list[Conflict] = []
    for key, items in groups.items():
        values = {_norm(item.claim_value) for item in items}
        if len(values) <= 1:
            continue

        source_ids = sorted({item.source_id for item in items})
        resolution = next(
            (
                f"{newer} explicitly supersedes {older}"
                for newer, older in superseded_pairs
                if newer in source_ids and older in source_ids
            ),
            None,
        )
        conflicts.append(
            Conflict(
                claim_key=key,
                values=sorted({item.claim_value for item in items}),
                source_ids=source_ids,
                conflict_type=_conflict_type(items),
                max_severity=max(item.severity for item in items),
                resolved=resolution is not None,
                resolution_basis=resolution,
            )
        )

    unresolved = [item for item in conflicts if not item.resolved]
    high_structural_conflict = any(
        item.conflict_type in {
            "DECISION_VS_GUIDANCE",
            "DECISION_VS_IMPLEMENTATION",
            "PROPOSAL_VS_DECISION",
        }
        for item in unresolved
    )
    operational_challenge = bool(challenged_sources)

    reason_codes: list[str] = []
    if unresolved:
        reason_codes.append("MATERIAL_CONTRADICTION")
    if high_structural_conflict:
        reason_codes.extend(["NO_CLEAR_SUPERSESSION", "AUTHORITY_AMBIGUITY"])
    if operational_challenge:
        reason_codes.append("RECENT_OPERATIONAL_CHALLENGE")

    if high_structural_conflict or operational_challenge or any(
        item.max_severity >= 4 for item in unresolved
    ):
        decision = Answerability.UNSAFE
        allowed_action = AllowedAction.BLOCK_AUTOMATION
        requires_human_review = True
        reason = "Material organizational disagreement is unresolved; human review is required."
    elif unresolved:
        decision = Answerability.CONDITIONAL
        allowed_action = AllowedAction.ANSWER_WITH_WARNING
        requires_human_review = False
        reason = "The evidence contains unresolved competing claims."
    else:
        decision = Answerability.SAFE
        allowed_action = AllowedAction.ANSWER
        requires_human_review = False
        reason_codes.append("NO_MATERIAL_CONFLICT")
        reason = "No material unresolved conflict was found in the supplied evidence."

    return EvaluationResult(
        decision=decision,
        allowed_action=allowed_action,
        requires_human_review=requires_human_review,
        reason_codes=reason_codes,
        reason=reason,
        conflicts=conflicts,
        evidence=request.evidence,
    )
