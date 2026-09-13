# ConflictLens

ConflictLens is a conflict-aware retrieval layer for enterprise AI systems. It prevents false consensus by preserving competing claims, provenance, and time before an agent answers.

## Core pipeline

1. Retrieve evidence.
2. Extract typed claims.
3. classify claim state.
4. Compare claim relations.
5. Return an answerability decision: `SAFE`, `CONDITIONAL`, or `UNSAFE`.

## Tomorrow's vertical slice

- Accept a question and a small set of evidence records.
- Detect exact conflicts between normalized claims.
- Preserve source and timestamp data.
- Return a decision with reasons and the claims that drove it.
- Run the included unit tests and expose the engine through FastAPI.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn conflictlens.api:app --reload
pytest
```

Open `http://localhost:8000/docs` for the API.

## Initial success criteria

- The engine never hides a detected high-severity conflict.
- Every output claim retains provenance.
- The same input produces the same policy decision.
- Tests cover safe, conditional, and unsafe outcomes.

## Planned evaluation

Conflict precision and recall, false-consensus rate, conflict-preservation rate, temporal accuracy, and answerability accuracy.

See [docs/PLAN.md](docs/PLAN.md) for the build order.