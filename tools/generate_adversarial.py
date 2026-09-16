"""Generate deterministic adversarial variants from frozen seed cases.

This generator does not call ConflictLens and does not inspect engine output.
Gold outcomes come from the seed case except near-miss controls, which are
constructed to remove the material disagreement and therefore use SAFE/ANSWER.
"""
import copy
import json
import random
from pathlib import Path

ROOT = Path(__file__).parents[1]
SEED = ROOT / "benchmark"
OUT = SEED / "adversarial" / "cases"
RNG_SEED = 20260916


def load_seed(case_id: str) -> dict:
    return json.loads((SEED / case_id / "case.json").read_text())


def write_variant(case: dict, family: str, index: int) -> None:
    case = copy.deepcopy(case)
    case["variant_family"] = family
    case["parent_case_id"] = case["case_id"]
    case["case_id"] = f'{case["case_id"]}-{family}-{index:02d}'
    path = OUT / f'{case["case_id"]}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(case, indent=2) + "\n")


def paraphrase(case: dict, index: int) -> dict:
    c = copy.deepcopy(case)
    prefixes = ["Current question: ", "Operationally, ", "Based on the supplied records, "]
    c["question"] = prefixes[index % len(prefixes)] + c["question"]
    return c


def distractor(case: dict, index: int) -> dict:
    c = copy.deepcopy(case)
    c["evidence"].append({
        "source_id": f"distractor-{index}",
        "claim_key": "unrelated maintenance window",
        "claim_value": "Saturday 02:00 UTC",
        "observed_at": "2026-09-01T00:00:00Z",
        "source_state": "GUIDANCE",
        "authority": 1,
        "severity": 1
    })
    return c


def metadata_ablation(case: dict) -> dict:
    c = copy.deepcopy(case)
    for e in c["evidence"]:
        e["source_state"] = "UNKNOWN"
    return c


def relation_ablation(case: dict) -> dict:
    c = copy.deepcopy(case)
    c["relations"] = []
    return c


def temporal_perturbation(case: dict, index: int) -> dict:
    c = copy.deepcopy(case)
    dates = ["2024-01-01T00:00:00Z", "2026-09-15T00:00:00Z"]
    if c["evidence"]:
        c["evidence"][index % len(c["evidence"])]["observed_at"] = dates[index % 2]
    return c


def authority_inversion(case: dict) -> dict:
    c = copy.deepcopy(case)
    for e in c["evidence"]:
        e["authority"] = 6 - int(e.get("authority", 1))
    return c


def order_permutation(case: dict, index: int) -> dict:
    c = copy.deepcopy(case)
    rng = random.Random(RNG_SEED + index + int(case["case_id"].split("-")[1]))
    rng.shuffle(c["evidence"])
    rng.shuffle(c["relations"])
    return c


def near_miss(case: dict, index: int) -> dict:
    c = copy.deepcopy(case)
    if not c["evidence"]:
        return c
    anchor = max(c["evidence"], key=lambda e: int(e.get("authority", 1)))
    for e in c["evidence"]:
        if e["claim_key"] == anchor["claim_key"]:
            e["claim_value"] = anchor["claim_value"]
    c["relations"] = [r for r in c["relations"] if r["type"] not in {"CHALLENGES", "CONTRADICTS"}]
    c["gold"] = {"decision":"SAFE","requires_human_review":False,"allowed_action":"ANSWER"}
    return c


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for n in range(1, 11):
        seed = load_seed(f"CL-{n:03d}")
        for i in range(3):
            write_variant(paraphrase(seed, i), "P", i + 1)
        for i in range(2):
            write_variant(distractor(seed, i), "D", i + 1)
        write_variant(metadata_ablation(seed), "M", 1)
        write_variant(relation_ablation(seed), "R", 1)
        for i in range(2):
            write_variant(temporal_perturbation(seed, i), "T", i + 1)
        for i in range(2):
            write_variant(near_miss(seed, i), "N", i + 1)
        write_variant(authority_inversion(seed), "A", 1)
        for i in range(3):
            write_variant(order_permutation(seed, i), "O", i + 1)

    generated = list(OUT.glob("*.json"))
    if len(generated) != 150:
        raise RuntimeError(f"expected 150 variants, generated {len(generated)}")
    print(f"generated {len(generated)} adversarial cases")


if __name__ == "__main__":
    main()
