# ConflictLens vNext development pack

Status: draft. Revision 0.3.0-draft.1. No model calls, scores, or completed human reviews.
This is independent research, not a hackathon deliverable.

The v0 pilot and its audit remain unchanged. This directory starts a different
measurement contract; its candidate labels must not replace the old labels in
the completed 800-response run. See `experiments/results/PAIRED_AUDIT_20260916.md`.

## What exists

`RUBRIC.md` separates answerability, conflict state, and action permission.
`development.json` contains 14 distinct inputs across seven paired parent scenarios.
Each input retains full synthetic source text, issue time, an explicit evaluation
time, and an exact proposed action or null. Candidate labels are proposals, not
gold truth. Every case is development-only, and every reviews array is empty.

The paired changes are approval absent/present, ban/explicit exception,
supersession present/absent, different/overlapping scopes, passing/failing pilot,
owner evidence present/missing, and capability-only/explicit authorization.
The retention pair uses exact configuration requirements, not two compatible
upper bounds. A failure under a conditional rollout policy is not automatically
a contradiction between that policy and the observed failure.

Some scenarios revisit problems exposed by the pilot. None can serve as an
independent held-out test. Fourteen case IDs are not fourteen independent samples;
the paired scenarios share seven parents. No sampling-adequacy claim is made.

## Offline commands

From the repository root with the project's dependencies installed:

```powershell
python .\tools\validate_vnext.py
python -m pytest .\tests\test_research_contract.py
python .\tools\prepare_vnext_review.py --output-dir .\review-packet-vnext
```

Validation checks strict JSON structure, enum values, real citation substrings,
source identity, timestamps, duplicate inputs, and parent/split boundaries.
It does not prove semantic correctness. Output must say `evaluation_release=BLOCKED`.
No installed model credentials are needed. There are no network calls in these tools.

`--release-check` deliberately exits 2 while review or held-out prerequisites are
missing. This is a readiness check, not the regular CI test. `--schema` prints the
response JSON schema. It does not check runtime citation references or human review.
Do not feed a candidate assessment to an inference pipeline and call that an
experiment; the contract module contains no inference engine.

The legacy model collector is preserved for reproduction. It does not enforce this
new preflight. Do not launch new paid experiments through that old collector.
A later vNext runner must explicitly require a reviewed, frozen manifest.

## Human annotation before evaluation

Share only the exported `RUBRIC.md`, `CASES.md`, and `inputs.jsonl` with annotators.
Do not share candidate labels or earlier model outputs before their first annotations.
The files are public development materials, so process records, not the export
alone, must support any claim of blinding.

Obtain two actual human annotations for each candidate evaluation case under the
same rubric. At least one reviewer must be independent of case construction.
Record reviewer IDs, relevant expertise, relationship to the author, time, exact
input hash, rubric hash, labels, cited quotes, and each axis rationale. Do not
count AI review as independent human annotation. The validator checks recorded
attestations, not identity, expertise, or whether reviewers were truly blinded.

Keep original annotations and disagreements. Adjudicate disagreements in a separate
versioned record; do not edit earlier reviews until they match. The current gate
blocks disagreement and does not yet implement an adjudication override.
Author revision after review creates a new input hash and requires renewed review.

## New evaluation set, not more variants of the same pilot

First review the task definition using these development cases. Author new parent
scenarios separately for evaluation. Keep all variants of a parent in one split;
do not reuse a pilot parent as held-out under a new ID. Freeze rubric, source inputs,
annotations, planned metrics, model configuration, and protocol before evaluating.
Do not call an exposed development case held-out after inspecting its scores.

For future paraphrases, change the claim wording and have people confirm semantic
preservation. For source-field ablations, retain source text when testing extraction;
otherwise explicitly reassess whether the visible task still supports the same
label. Do not propagate labels just because a generator did not call an engine.
Check exact and order-insensitive duplicates; document correlated paraphrases and
scope variants rather than counting them as independent observations.

## Experimental controls to implement next

Both methods receive the same rubric and source bundle. Separate an oracle-annotation
policy test from an end-to-end raw-text pipeline test. Hand-labeled relations are
an oracle input, not an extraction capability. Log the actual request and response,
content hashes, code revision, real model name and snapshot, deployment, timestamps,
completion status, settings (including provider defaults), usage, and retries.
Record parser/schema errors; never choose a label by matching explanation words.

Score each axis and joint label agreement separately. For proposed operations,
report PERMITTED predictions on reviewed PROHIBITED cases, approval-bypass predictions,
and unsupported grants on UNDETERMINED cases as separate rates with denominators.
Measure unnecessary withholding on reviewed PERMITTED cases. A textual refusal must
not become a dangerous action just because the answer is determinate. Actual action
safety would require an executor and observed tool outcomes, neither supplied here.

Use parent-aware analysis. Repeated model calls measure stability, not added parent
scenarios. A new baseline should include an explicit same-policy prompt and appropriate
simple policy baselines; the old prompt remains part of the legacy pilot only.
No second-model run is warranted until these task and data controls are ready.

## AI use

AI assistance drafted the rubric, synthetic examples, candidate labels, schema,
validation code, tests, and these instructions. Executed software tests validate
format and stated invariants only. No human authorship of the draft annotations,
independent human review, or validated empirical advantage is claimed. The author
must verify the work and disclose material AI use in the eventual submission.
