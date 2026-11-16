#!/usr/bin/env python3
"""
Orchestrator script to execute Advanced Attack Benchmark k=3 for any provider/model:
- With --tag <tag> (recommended): runs <tag>_adv_r1, <tag>_adv_r2, <tag>_adv_r3
- Legacy default (no --tag/--rounds): runs advanced_benchmark_r2, advanced_benchmark_r3
- Synthesizes k=3 results (ASR, SUP, MHR, FDR, UA, Delta U, Track B) via synthesize_attack_k3.py
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PYTHON_EXE = sys.executable
ADV_DIR = Path(__file__).resolve().parent
AI_BACKEND = ADV_DIR.parents[2]
MODELS_DIR = AI_BACKEND / "benchmarkv2_refined" / "models"
DEFAULT_DATASET = "benchmarkv2_refined/framework/attack_advanced/data/advanced_attack_testcases.json"

ENV = os.environ.copy()
ENV["PYTHONIOENCODING"] = "utf-8"


def _slugify(model_name: str) -> str:
    return (
        model_name.strip()
        .replace(":", "_")
        .replace("/", "_")
        .replace("-", "_")
        .replace(".", "_")
    )


def _resolve_bu(benign_baseline: float | None, benign_summary: Path | None) -> float:
    if benign_baseline is not None:
        return float(benign_baseline)
    if benign_summary is not None and benign_summary.exists():
        data = json.loads(benign_summary.read_text(encoding="utf-8"))
        for key in ("ba_overall", "mean_ba", "benign_baseline_fixed_bu"):
            if key in data and data[key] is not None:
                return float(data[key])
    return 0.9300


def run_round(
    run_id: str,
    dataset: str,
    provider: str,
    model: str,
    timeout: float,
    benign_baseline: float,
    limit: int | None,
    use_mock_rag: bool,
) -> bool:
    print(f"\n{'='*70}\n>>> START ADVANCED ATTACK ROUND: {run_id} (provider={provider}, model={model})\n{'='*70}", flush=True)
    cmd = [
        PYTHON_EXE, "-m", "benchmarkv2_refined.framework.attack_advanced.runner.run_advanced_attack",
        "--run-id", run_id,
        "--dataset", dataset,
        "--provider", provider,
        "--model", model,
        "--timeout", str(timeout),
        "--benign-baseline", str(benign_baseline),
    ]
    if limit is not None:
        cmd.extend(["--limit", str(limit)])
    if use_mock_rag:
        cmd.append("--use-mock-rag")

    t0 = time.time()
    res = subprocess.run(cmd, cwd=str(AI_BACKEND), env=ENV)
    elapsed = time.time() - t0
    if res.returncode != 0:
        print(f"[!] Error running {run_id} (code={res.returncode}, elapsed={elapsed:.1f}s)", flush=True)
        return False
    print(f"[✓] Finished {run_id} in {elapsed/60:.1f} minutes", flush=True)
    return True


def synthesize(prefix: str | None, model: str, benign_baseline: float, rounds: list[str]) -> None:
    print(f"\n{'='*70}\n>>> SYNTHESIZING K=3 ADVANCED ATTACKS ({model})\n{'='*70}", flush=True)
    cmd = [
        PYTHON_EXE, str(ADV_DIR / "synthesize_attack_k3.py"),
        "--model-name", model,
        "--benign-baseline", str(benign_baseline),
    ]
    runs_dir = MODELS_DIR / _slugify(model) / "attack_advanced"
    cmd.extend(["--runs-dir", str(runs_dir)])
    if prefix:
        cmd.extend(["--run-prefix", prefix])
    elif len(rounds) == 3:
        cmd.extend([
            "--r1", str(runs_dir / rounds[0] / "eval_advanced_attack.json"),
            "--r2", str(runs_dir / rounds[1] / "eval_advanced_attack.json"),
            "--r3", str(runs_dir / rounds[2] / "eval_advanced_attack.json"),
        ])

    res = subprocess.run(cmd, cwd=str(AI_BACKEND), env=ENV)
    if res.returncode == 0:
        print("[✓] Synthesis successful!", flush=True)
    else:
        print(f"[!] Synthesis error (code={res.returncode})", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Run Advanced Attack Benchmark k=3 pipeline")
    parser.add_argument("--provider", default="ollama", choices=["ollama", "gemini", "deepseek", "openai", "anthropic", "zhipu"])
    parser.add_argument("--model", default="gemini-3.5-flash-lite", help="Tên model (vd: deepseek-flash, qwen2.5:7b, qwen3:8b)")
    parser.add_argument("--tag", default=None, help="Prefix tên model (vd: deepseek_flash -> chạy <tag>_adv_r1..r3)")
    parser.add_argument("--rounds", nargs="+", default=None, help="Danh sách run-id tùy chọn")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--benign-baseline", type=float, default=None, help="BU của model (từ Benign Benchmark)")
    parser.add_argument("--benign-summary", type=Path, default=None, help="Đường dẫn k3_benign_summary_*.json hoặc summary.json")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--use-mock-rag", action="store_true", default=False)
    parser.add_argument("--synthesize-only", action="store_true", default=False)

    args = parser.parse_args()
    tag = args.tag or (_slugify(args.model) if args.provider in ("ollama", "deepseek") else None)
    prefix = f"{tag}_adv" if tag else None

    if args.rounds:
        rounds = args.rounds
    elif prefix:
        rounds = [f"{prefix}_r1", f"{prefix}_r2", f"{prefix}_r3"]
    else:
        rounds = ["advanced_benchmark_r2", "advanced_benchmark_r3"]

    bu = _resolve_bu(args.benign_baseline, args.benign_summary)
    print(f"Launching K=3 Advanced Attack Benchmark: provider={args.provider}, model={args.model}, BU={bu*100:.2f}%, rounds={rounds}", flush=True)

    if not args.synthesize_only:
        for rid in rounds:
            ok = run_round(
                run_id=rid,
                dataset=args.dataset,
                provider=args.provider,
                model=args.model,
                timeout=args.timeout,
                benign_baseline=bu,
                limit=args.limit,
                use_mock_rag=args.use_mock_rag,
            )
            if not ok:
                print(f"[!] Pipeline halted due to error in {rid}.", flush=True)
                sys.exit(1)

    synthesize(prefix=prefix, model=args.model, benign_baseline=bu, rounds=rounds)
    print("\n[✓] ALL K=3 ADVANCED ATTACK RUNS AND SYNTHESIS COMPLETED!", flush=True)


if __name__ == "__main__":
    main()
