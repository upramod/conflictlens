# Adversarial benchmark protocol

The seed benchmark is intentionally small. A perfect score on ten hand-authored cases is not evidence of generalization.

Adversarial evaluation expands each seed case without changing the underlying organizational state. Gold labels are assigned before engine evaluation and are not changed to fit implementation output.

## Variant families

1. **Paraphrase**. Change wording while preserving the same claim semantics.
2. **Distractor**. Add topically related evidence that does not resolve the target conflict.
3. **Metadata ablation**. Remove source-state metadata to measure dependence on typed provenance.
4. **Relation ablation**. Remove explicit SUPPORTS, CONTRADICTS, SUPERSEDES, or CHALLENGES edges.
5. **Temporal perturbation**. Move timestamps while preserving or changing the valid supersession order.
6. **Near-miss control**. Construct similar-looking evidence where blocking is incorrect.
7. **Authority inversion**. Make the newer source less authoritative or the older source more authoritative without inventing supersession.
8. **Evidence-order permutation**. Reorder records. Deterministic ConflictLens output must remain unchanged.

## Primary metrics

- Answerability accuracy
- Unsafe recall
- Unsafe precision
- False-consensus rate
- False-block rate
- Action accuracy
- Conflict-preservation rate
- Order invariance

## Evaluation rule

Seed cases and generated variants are frozen before the prompt-only baseline is run. Engine changes after an evaluation round receive a new version label. Results from earlier versions remain recorded.
