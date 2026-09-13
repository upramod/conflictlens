# Build plan

## Day 1. Working slice

1. Run the API and baseline tests.
2. Add a demo evidence set with one safe, one conditional, and one unsafe case.
3. Replace exact-value comparison with typed relation rules.
4. Add a small reviewer screen only after the policy output is stable.

## Next

- Claim extraction adapter with a deterministic fixture mode.
- Temporal supersession and authority rules.
- Relation types: supports, contradicts, supersedes, and scopes.
- Structured audit record for every decision.
- Benchmark runner against plain RAG and prompt-only contradiction checks.

## Deferred

Authentication, enterprise connectors, vector infrastructure, and model tuning. They do not belong in the first demo.
