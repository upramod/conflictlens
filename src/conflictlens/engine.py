from collections import defaultdict

from .models import Answerability, Conflict, EvaluationRequest, EvaluationResult


def _norm(value: str) -> str:
    return " ".join(value.casefold().split())


def evaluate(request: EvaluationRequest) -> EvaluationResult:
    groups = defaultdict(list)
    for item in request.evidence:
        groups[_norm(item.claim_key)].append(item)

    conflicts: list[Conflict] = []
    for key, items in groups.items():
        values = {_norm(item.claim_value) for item in items}
        if len(values) > 1:
            conflicts.append(
                Conflict(
                    claim_key=key,
                    values=sorted({item.claim_value for item in items}),
                    source_ids=sorted({item.source_id for item in items}),
                    max_severity=max(item.severity for item in items),
                )
            )

    if any(item.max_severity >= 4 for item in conflicts):
        decision = Answerability.UNSAFE
        reason = "A high-severity conflict requires human review."
    elif conflicts:
        decision = Answerability.CONDITIONAL
        reason = "The evidence contains unresolved competing claims."
    else:
        decision = Answerability.SAFE
        reason = "No direct conflict was found in the supplied evidence."

    return EvaluationResult(
        decision=decision,
        reason=reason,
        conflicts=conflicts,
        evidence=request.evidence,
    )
