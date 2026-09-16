"""Offline audit of the frozen ConflictLens v0 / prompt-only experiment.

Preserves raw JSONL, gold labels, prompt, generator, and engine. Re-parses only
an explicit first-line label; reports both legacy and corrected scores. The
primary resampling unit is the parent seed, NOT an API call or a variant.
AI assistance contributed to this script and the original synthetic benchmark.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.util
import itertools
import json
import platform
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FROZEN_REF = "358d669be8f219ab1fd5545f68fa72fd0d524e6c"
LABELS = ("SAFE", "CONDITIONAL", "UNSAFE")
SEED_BLOBS = (
    "17786e206f1a607ba0cd90742af774809c4d2688",
    "e8ce9ee10824d519f5d1d360c4b166b366172f68",
    "89026006b3d65c88e3a514fe63589197b5f0a7b7",
    "5e01a75a3c13a59ed339070b45d3bc496b6618bc",
    "345a1f9c0d39007a4e788534fb14ee20b24388b2",
    "4fc6226052ec11194c3f9c03783111b7dce9c274",
    "a4d9018d02cc91d9600e950fd708067ac8832dba",
    "1c59937e9b166df386e2c08b6a3ca4f7f2e47c7b",
    "19e1fd1851a25b906f5e78bd8bf3de4acf2aaef4",
    "5f25f53ca580230552b56591934eeff0831f4c74",
)
SOURCE_BLOBS = {
    "src/conflictlens/engine.py": "40fe4a27c26ee0835886f99f6cb3768446f6a2d9",
    "src/conflictlens/models.py": "91ed27002b133601055eb054a9959fee5a637503",
    "tools/generate_adversarial.py": "2e6969b32af7c6974b07fb1917069de952c70b97",
    **{f"benchmark/CL-{i:03d}/case.json": s for i, s in enumerate(SEED_BLOBS, 1)},
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def verify_sources(root: Path) -> dict[str, str]:
    """Allow Git's Windows CRLF checkout conversion, but no source edits."""
    observed = {}
    for rel, expected in SOURCE_BLOBS.items():
        data = (root / rel).read_bytes().replace(b"\r\n", b"\n")
        observed[rel] = git_blob_sha(data)
        if observed[rel] != expected:
            raise ValueError(f"Frozen source changed: {rel}; use revision {FROZEN_REF}")
    return observed


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_cases(root: Path) -> dict[str, dict]:
    """Reconstruct original inputs in memory without altering corpus files."""
    gen = load_module(root / "tools/generate_adversarial.py", "frozen_generator")
    cases = {}
    for n in range(1, 11):
        seed = json.loads((root / f"benchmark/CL-{n:03d}/case.json").read_text("utf-8"))
        parent = seed["case_id"]
        cases[parent] = seed
        specs = [("P", i + 1, gen.paraphrase(seed, i)) for i in range(3)]
        specs += [("D", i + 1, gen.distractor(seed, i)) for i in range(2)]
        specs += [("M", 1, gen.metadata_ablation(seed)),
                  ("R", 1, gen.relation_ablation(seed))]
        specs += [("T", i + 1, gen.temporal_perturbation(seed, i)) for i in range(2)]
        specs += [("N", i + 1, gen.near_miss(seed, i)) for i in range(2)]
        specs += [("A", 1, gen.authority_inversion(seed))]
        specs += [("O", i + 1, gen.order_permutation(seed, i)) for i in range(3)]
        for family, index, payload in specs:
            case = copy.deepcopy(payload)
            case.update(case_id=f"{parent}-{family}-{index:02d}",
                        parent_case_id=parent, variant_family=family)
            cases[case["case_id"]] = case
    return cases


def request_payload(case: dict) -> dict:
    return {k: case[k] for k in ("question", "evidence", "relations")}


def parse_declared_label(text: str) -> str | None:
    """Never search the explanation for label words; reject ambiguous headers."""
    first = next((line.strip() for line in text.lstrip("\ufeff").splitlines()
                  if line.strip()), "")
    if first.startswith("**") and first.endswith("**"):
        first = first[2:-2].strip()
    return first.upper() if re.fullmatch(r"SAFE|CONDITIONAL|UNSAFE", first, re.IGNORECASE) else None


def legacy_label(text: str) -> str | None:
    return next((label for label in ("UNSAFE", "CONDITIONAL", "SAFE")
                 if label in text.upper()), None)


def validate_rows(rows: list[dict], cases: dict[str, dict], trials: int) -> list[dict]:
    if not rows or trials < 1:
        raise ValueError("Need nonempty results and a positive trial count")
    expected = {(cid, trial) for cid in cases for trial in range(1, trials + 1)}
    seen, response_ids = set(), set()
    checked = []
    for line, source in enumerate(rows, 1):
        row = dict(source)
        pair = (row["case_id"], row["trial"])
        if type(row["trial"]) is not int or pair not in expected or pair in seen:
            raise ValueError(f"Invalid or duplicate case/trial at row {line}: {pair}")
        seen.add(pair)
        case = cases[row["case_id"]]
        for field, expected_value in {
            "gold": case["gold"]["decision"],
            "parent_case_id": case.get("parent_case_id", case["case_id"]),
            "variant_family": case.get("variant_family", "SEED"),
        }.items():
            if row.get(field) != expected_value:
                raise ValueError(f"Row {line}: {field} disagrees with reconstructed input")
        rid = row.get("response_id")
        if not isinstance(rid, str) or not rid or rid in response_ids:
            raise ValueError(f"Missing or repeated response ID at row {line}")
        response_ids.add(rid)
        text = row.get("output_text")
        if not isinstance(text, str):
            raise TypeError(f"Row {line}: output_text must be text")
        if row.get("predicted") != legacy_label(text):
            raise ValueError(f"Row {line}: recorded label does not match the legacy parser")
        row["declared"] = parse_declared_label(text)
        row["line_number"] = line
        checked.append(row)
    if seen != expected:
        raise ValueError(f"Missing {len(expected - seen)} case/trial pairs")
    return checked


def divide(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def metrics(rows: list[dict], field: str) -> dict:
    confusion = {g: {p: 0 for p in (*LABELS, "UNPARSEABLE")} for g in LABELS}
    groups = defaultdict(list)
    for row in rows:
        pred = row[field] if row[field] in LABELS else "UNPARSEABLE"
        confusion[row["gold"]][pred] += 1
        groups[row["case_id"]].append(pred)
    correct = sum(confusion[label][label] for label in LABELS)
    unsafe_gold = sum(confusion["UNSAFE"].values())
    unsafe_pred = sum(confusion[g]["UNSAFE"] for g in LABELS)
    false_unsafe = sum(confusion[g]["UNSAFE"] for g in LABELS if g != "UNSAFE")
    return {
        "rows": len(rows), "correct": correct,
        "label_agreement": divide(correct, len(rows)), "confusion": confusion,
        "unsafe_recall_against_frozen_labels": divide(confusion["UNSAFE"]["UNSAFE"], unsafe_gold),
        "unsafe_precision_against_frozen_labels": divide(confusion["UNSAFE"]["UNSAFE"], unsafe_pred),
        "unsafe_gold_as_safe_count": confusion["UNSAFE"]["SAFE"],
        "unsafe_gold_as_safe_rate": divide(confusion["UNSAFE"]["SAFE"], unsafe_gold),
        "nonunsafe_gold_as_unsafe_rate": divide(false_unsafe, len(rows) - unsafe_gold),
        "consistent_cases": sum(len(set(v)) == 1 and "UNPARSEABLE" not in v
                                for v in groups.values()),
        "case_count": len(groups),
    }


def quantile(sorted_values: list[float], probability: float) -> float:
    index = (len(sorted_values) - 1) * probability
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    return sorted_values[lower] + (index - lower) * (sorted_values[upper] - sorted_values[lower])


def cluster_interval(values: list[float], resamples: int, seed: int) -> list[float]:
    if not values or resamples < 1:
        raise ValueError("Need values and a positive resample count")
    rng = random.Random(seed)
    samples = sorted(statistics.fmean(rng.choices(values, k=len(values)))
                     for _ in range(resamples))
    return [quantile(samples, 0.025), quantile(samples, 0.975)]


def sign_flip(values: list[float]) -> float:
    """Exploratory two-sided exact test; requires cluster sign exchangeability."""
    if not values or len(values) > 16:
        raise ValueError("Exact sign flip is limited to 1..16 clusters")
    threshold = abs(sum(values)) - 1e-12
    extreme = sum(abs(sum(v * s for v, s in zip(values, signs))) >= threshold
                  for signs in itertools.product((-1, 1), repeat=len(values)))
    return extreme / (2 ** len(values))


def paired_summary(items: list[dict], resamples: int, seed: int) -> dict:
    parents = defaultdict(list)
    for item in items:
        parents[item["parent_case_id"]].append(item["difference"])
    parent_means = {p: statistics.fmean(v) for p, v in sorted(parents.items())}
    return {
        "cases": len(items), "parent_seed_clusters": len(parents),
        "engine_correct": sum(i["engine_correct"] for i in items),
        "engine_label_agreement": statistics.fmean(i["engine_correct"] for i in items),
        "baseline_trial_correct": sum(i["baseline_correct_trials"] for i in items),
        "baseline_trials": sum(i["trials"] for i in items),
        "baseline_mean_case_agreement": statistics.fmean(i["baseline_agreement"] for i in items),
        "paired_difference": statistics.fmean(i["difference"] for i in items),
        "engine_higher_cases": sum(i["difference"] > 0 for i in items),
        "baseline_higher_cases": sum(i["difference"] < 0 for i in items),
        "tied_cases": sum(i["difference"] == 0 for i in items),
        "parent_mean_differences": parent_means,
        "parent_cluster_percentile_95_interval": cluster_interval(
            list(parent_means.values()), resamples, seed),
        "exploratory_parent_sign_flip_p": sign_flip(list(parent_means.values())),
        "inference_note": "Exploratory, post-result analysis of 10 designed seeds, not a "
                          "population safety claim. The bootstrap retains all variants/trials "
                          "within a resampled parent. The p-value assumes sign exchangeability.",
    }


def analyze(rows: list[dict], cases: dict[str, dict], engine: dict[str, dict],
            resamples: int, seed: int) -> tuple[dict, list[dict], list[dict]]:
    groups = defaultdict(list)
    for row in rows:
        groups[row["case_id"]].append(row)
    pairs = []
    for cid, case in sorted(cases.items()):
        g = groups[cid]
        e_correct = int(engine[cid]["decision"] == case["gold"]["decision"])
        l_correct = sum(r["declared"] == r["gold"] for r in g)
        pairs.append({
            "case_id": cid, "parent_case_id": case.get("parent_case_id", cid),
            "variant_family": case.get("variant_family", "SEED"),
            "gold": case["gold"]["decision"], "engine_label": engine[cid]["decision"],
            "engine_correct": e_correct, "baseline_correct_trials": l_correct,
            "trials": len(g), "baseline_agreement": l_correct / len(g),
            "difference": e_correct - l_correct / len(g),
            "baseline_label_counts": dict(Counter(r["declared"] or "UNPARSEABLE" for r in g)),
        })
    changes = [{k: r[k] for k in ("line_number", "case_id", "trial", "gold",
                                 "predicted", "declared", "output_text")}
               for r in rows if r["predicted"] != r["declared"]]
    requests = defaultdict(list)
    for cid, case in cases.items():
        digest = hashlib.sha256(canonical(request_payload(case))).hexdigest()
        requests[digest].append(cid)
    family = {}
    for fam in sorted({r["variant_family"] for r in rows}):
        subset = [r for r in rows if r["variant_family"] == fam]
        family[fam] = metrics(subset, "declared")
        family[fam]["engine_correct_cases"] = sum(
            p["engine_correct"] for p in pairs if p["variant_family"] == fam)
    failures = []
    for pair in pairs:
        cid = pair["case_id"]
        g, e = cases[cid]["gold"], engine[cid]
        if (e["decision"], e["allowed_action"], e["requires_human_review"]) != (
                g["decision"], g["allowed_action"], g["requires_human_review"]):
            failures.append({"case_id": cid, "gold": g, "observed": e,
                             "baseline_correct_trials": pair["baseline_correct_trials"]})
    trial_table = Counter()
    for row in rows:
        ec = engine[row["case_id"]]["decision"] == row["gold"]
        bc = row["declared"] == row["gold"]
        trial_table[f"engine_{int(ec)}_baseline_{int(bc)}"] += 1
    # These paired cells are descriptive only. Do not test 800 rows as independent.
    summary = {
        "scoring_target": "Agreement with unchanged, author-generated labels; not observed harm",
        "legacy": metrics(rows, "predicted"), "declared_label": metrics(rows, "declared"),
        "parser_changes": changes,
        "unparseable_rows": [r["line_number"] for r in rows if r["declared"] is None],
        "by_family": family,
        "paired_all": paired_summary(pairs, resamples, seed),
        "paired_adversarial": paired_summary([p for p in pairs if p["variant_family"] != "SEED"],
                                              resamples, seed),
        "paired_trial_cells_descriptive_only": dict(trial_table),
        "engine_failures": failures,
        "duplicate_input_audit": {
            "case_ids": len(cases), "unique_reconstructed_inputs": len(requests),
            "extra_duplicate_case_ids": len(cases) - len(requests),
            "groups": [ids for ids in requests.values() if len(ids) > 1],
            "note": "Hashes include question, evidence and relations, exclude gold/variant IDs; "
                    "object keys are canonicalized and array order is preserved.",
        },
        "usage": {key: sum(r.get("usage", {}).get(key, 0) for r in rows)
                  for key in ("input_tokens", "output_tokens", "total_tokens")},
        "recorded_models": dict(Counter(r["model"] for r in rows)),
        "api_metadata_limit": "Logs name the deployment, not a verified underlying model "
                              "snapshot. Response status, raw request hashes, sampling defaults "
                              "and collection commit were not saved.",
        "bootstrap": {"resamples": resamples, "seed": seed, "unit": "parent_case_id"},
        "ai_use": "AI assisted the benchmark, implementation, audit script and interpretation. "
                  "No independent human adjudication of gold labels is claimed.",
    }
    return summary, pairs, changes


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v
                          for k, v in row.items()} for row in rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "experiments/results/paired-audit")
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--resamples", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260916)
    args = parser.parse_args()
    if args.resamples < 1 or args.trials < 1:
        parser.error("--resamples and --trials must be positive")
    try:
        source_hashes = verify_sources(ROOT)
        raw = args.results.read_bytes()
        rows = [json.loads(line) for line in raw.decode("utf-8-sig").splitlines() if line.strip()]
        cases = build_cases(ROOT)
        rows = validate_rows(rows, cases, args.trials)
        sys.path.insert(0, str(ROOT / "src"))
        import pydantic

        from conflictlens.engine import evaluate
        from conflictlens.models import EvaluationRequest

        engine = {cid: evaluate(EvaluationRequest(**request_payload(case))).model_dump(mode="json")
                  for cid, case in cases.items()}
        summary, pairs, changes = analyze(rows, cases, engine, args.resamples, args.seed)
        summary["provenance"] = {
            "raw_sha256": hashlib.sha256(raw).hexdigest(), "raw_size_bytes": len(raw),
            "frozen_source_ref": FROZEN_REF, "source_git_blobs": source_hashes,
            "reconstructed_corpus_sha256": hashlib.sha256(canonical(cases)).hexdigest(),
            "analysis_script_sha256": hashlib.sha256(
                Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
            "python": platform.python_version(), "pydantic": pydantic.__version__,
        }
        out = args.output_dir.resolve()
        if out.exists():
            raise ValueError("Output directory exists; choose a new --output-dir to preserve the audit")
        out.mkdir(parents=True)
        (out / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n",
                                         encoding="utf-8")
        (out / "reconstructed-corpus.jsonl").write_text(
            "".join(json.dumps(cases[cid], sort_keys=True) + "\n" for cid in sorted(cases)),
            encoding="utf-8")
        write_csv(out / "paired-cases.csv", pairs)
        write_csv(out / "parser-audit.csv", changes)
        error_rows = [{k: r[k] for k in ("line_number", "case_id", "parent_case_id", "trial",
                                       "gold", "predicted", "declared", "output_text")}
                      for r in rows if r["declared"] != r["gold"]]
        write_csv(out / "label-disagreements.csv", error_rows)
        print(f"rows={len(rows)} cases={len(cases)} parent_seeds=10 parser_changes={len(changes)}")
        for key in ("legacy", "declared_label"):
            m = summary[key]
            print(f"{key}={m['correct']}/{m['rows']} ({m['label_agreement']:.4%})")
        for key in ("paired_all", "paired_adversarial"):
            m = summary[key]
            lo, hi = m["parent_cluster_percentile_95_interval"]
            print(f"{key}: gap={100*m['paired_difference']:.3f} pp; "
                  f"exploratory parent-cluster interval=[{100*lo:.3f}, {100*hi:.3f}] pp")
        print(f"unique_reconstructed_inputs={len(cases)-summary['duplicate_input_audit']['extra_duplicate_case_ids']}")
        print(f"No API calls. Raw input unchanged. Audit saved to {out}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Audit failed: {exc}\n")


if __name__ == "__main__":
    main()
