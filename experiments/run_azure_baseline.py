"""Run the frozen prompt-only baseline against Azure OpenAI Responses API."""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parents[1]
PROMPT = ROOT / "experiments" / "prompts" / "strong_prompt_baseline.txt"
SEEDS = ROOT / "benchmark"
ADV = ROOT / "benchmark" / "adversarial" / "cases"
DEFAULT_ENDPOINT = "https://conflictlens.openai.azure.com/openai/responses?api-version=2025-04-01-preview"
DEFAULT_MODEL = "conflictlens-gpt56-luna"


def cases() -> list[Path]:
    subprocess.run([sys.executable, str(ROOT / "tools" / "generate_adversarial.py")], check=True)
    seed = sorted(SEEDS.glob("CL-*/case.json"))
    adv = sorted(ADV.glob("*.json"))
    if len(seed) != 10 or len(adv) != 150:
        raise RuntimeError(f"expected 10 seed + 150 adversarial; got {len(seed)} + {len(adv)}")
    return seed + adv


def evidence_text(case: dict) -> str:
    return json.dumps({
        "question": case["question"],
        "evidence": case["evidence"],
        "relations": case.get("relations", []),
    }, indent=2)


def output_text(response: dict) -> str:
    chunks = []
    for item in response.get("output", []):
        for part in item.get("content", []):
            if part.get("type") == "output_text":
                chunks.append(part.get("text", ""))
    return "\n".join(chunks).strip()


def label(text: str) -> str | None:
    upper = text.upper()
    for candidate in ("UNSAFE", "CONDITIONAL", "SAFE"):
        if candidate in upper:
            return candidate
    return None


def call(endpoint: str, key: str, model: str, prompt: str, case: dict) -> dict:
    body = json.dumps({
        "model": model,
        "instructions": prompt,
        "input": evidence_text(case),
        "max_output_tokens": 700,
    }).encode()
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json", "api-key": key},
        method="POST",
    )
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 5:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--endpoint", default=os.getenv("AZURE_OPENAI_ENDPOINT", DEFAULT_ENDPOINT))
    parser.add_argument("--model", default=os.getenv("AZURE_OPENAI_DEPLOYMENT", DEFAULT_MODEL))
    parser.add_argument("--output", default="experiments/results/gpt56-luna-baseline.jsonl")
    args = parser.parse_args()
    key = os.getenv("AZURE_OPENAI_API_KEY")
    if not key:
        raise SystemExit("AZURE_OPENAI_API_KEY is not set")
    prompt = PROMPT.read_text()
    paths = cases()
    if args.limit:
        paths = paths[: args.limit]
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    completed = set()
    if out.exists():
        for line in out.read_text().splitlines():
            row = json.loads(line)
            completed.add((row["case_id"], row["trial"]))
    with out.open("a", encoding="utf-8") as handle:
        for path in paths:
            case = json.loads(path.read_text())
            for trial in range(1, args.trials + 1):
                if (case["case_id"], trial) in completed:
                    continue
                response = call(args.endpoint, key, args.model, prompt, case)
                text = output_text(response)
                row = {
                    "case_id": case["case_id"],
                    "parent_case_id": case.get("parent_case_id", case["case_id"]),
                    "variant_family": case.get("variant_family", "SEED"),
                    "trial": trial,
                    "gold": case["gold"]["decision"],
                    "predicted": label(text),
                    "response_id": response.get("id"),
                    "model": response.get("model", args.model),
                    "output_text": text,
                    "usage": response.get("usage"),
                }
                handle.write(json.dumps(row) + "\n")
                handle.flush()
                print(f'{case["case_id"]} trial={trial}: {row["predicted"]} gold={row["gold"]}')


if __name__ == "__main__":
    main()
