# Experimental results

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
