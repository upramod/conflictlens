# ConflictLens benchmark

This benchmark tests whether an answerability layer preserves organizational disagreement instead of collapsing it into false consensus.

Gold cases:

| Case | Failure mode | Gold |
|---|---|---|
| CL-001 | Approved decision vs newer guidance, with operational challenge | UNSAFE |
| CL-002 | Retention policy vs stale guidance and implementation | UNSAFE |
| CL-003 | Proposed deprecation mistaken for an approved decision | CONDITIONAL |
| CL-004 | Release approval predates a rollback and current production state | UNSAFE |
| CL-005 | Explicit approved supersession | SAFE |
| CL-006 | Independent sources agree | SAFE |
| CL-007 | Design intent challenged by recent operational evidence | UNSAFE |
| CL-008 | Ownership disagreement without explicit transition evidence | CONDITIONAL |
| CL-009 | Stale guidance explicitly superseded by approved migration | SAFE |
| CL-010 | General automation permission conflicts with a specific human-approval policy | UNSAFE |

The gold labels are defined before model evaluation. They must not be changed merely to match current engine behavior.

Primary evaluation compares standard answer generation, a strong prompt-only contradiction baseline, and structured ConflictLens. Metrics include answerability accuracy, false-consensus rate, conflict preservation, and appropriate abstention.