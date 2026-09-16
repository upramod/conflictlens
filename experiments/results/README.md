# Experimental results

## Audit notice, 2026-09-16 UTC

Read [the paired analysis and measurement audit](PAIRED_AUDIT_20260916.md) before using these scores in a manuscript. An explanation-wide parser error affects one row. Derived declared-label agreement is **542/800 (67.750%)**, rather than the legacy **543/800**. Raw responses and original stored labels remain unchanged.

The 123 UNSAFE-gold/SAFE-prediction rows are label disagreements, not verified dangerous actions. Some SAFE responses explicitly deny authorization. The 160 case IDs contain 127 distinct reconstructed inputs from ten parent seeds. This round is an exploratory pilot. Do not claim established action-safety improvements or semantic/temporal robustness from these scores.

Use `python experiments/analyze_paired.py <raw-jsonl>` for the audited paired comparison. It makes no API calls and writes separate derived artifacts. The script verifies the frozen engine, schema, generator and seed hashes. Independent human label review and an actual underlying-model snapshot are still needed.

## Preserved original result summary

Raw model outputs are retained as immutable JSONL experiment records. Do not edit rows after a run. Each row records case ID, trial, gold label, predicted label, response ID, returned model identifier, raw output text, and token usage.

## GPT-5.6 Luna baseline, 2026-09-15

Configuration:
- Azure deployment: `conflictlens-gpt56-luna`
- Deployment type: Global Standard
- API: Azure OpenAI Responses API
- Prompt: `experiments/prompts/strong_prompt_baseline.txt`
- Trials: 5 per case
- Cases: 10 seeds + 150 deterministic adversarial variants = 160
- Responses: 800 unique `(case_id, trial)` pairs

Observed aggregate metrics from the frozen raw file:
- Accuracy: 543/800 (67.875%)
- UNSAFE recall: 210/350 (60.0%)
- UNSAFE precision: 210/292 (71.918%)
- UNSAFE mislabeled SAFE: 123 trials
- Exact five-trial label consistency: 121/160 cases (75.625%)

Family accuracy:
- SEED: 31/50 (62.0%)
- A authority inversion: 35/50 (70.0%)
- D distractor: 67/100 (67.0%)
- M metadata ablation: 37/50 (74.0%)
- N near-miss control: 86/100 (86.0%)
- O order permutation: 102/150 (68.0%)
- P paraphrase: 95/150 (63.333%)
- R relation ablation: 24/50 (48.0%)
- T temporal perturbation: 66/100 (66.0%)

Use `python experiments/score_baseline.py <raw-jsonl>` to reproduce the aggregate scoring. The raw JSONL is intentionally not summarized into replacement labels. Preserve it as primary experimental evidence.
