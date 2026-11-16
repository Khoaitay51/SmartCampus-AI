#!/usr/bin/env python3
"""
Orchestrator script to execute Clean Twin SUP k=3 rounds strictly following PLAN_CLEAN_TWIN_SUP_K3.md:
- Flexible for any --provider / --model / --tag
- Automatically invokes clean_twin_sup.py against the corresponding attack r1 runs
"""
from __future__ import annotations

import argparse
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
AI_BACKEND = Path(__file__).resolve().parents[3]
MODELS_DIR = AI_BACKEND / "benchmarkv2_refined" / "models"

DATASET = "benchmarkv2_refined/framework/attack_advanced/data/clean_twin_sup_testcases.json"

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


def run_round(
    run_id: str,
    provider: str,
    model: str,
    timeout: float,
    limit: int | None,
    use_mock_rag: bool,
    dataset: str = DATASET,
) -> bool:
    print(f"\n{'='*70}\n>>> START CLEAN TWIN SUP ROUND: {run_id} (provider={provider}, model={model})\n{'='*70}", flush=True)
    cmd = [
        PYTHON_EXE, "-m", "benchmarkv2_refined.framework.attack_advanced.runner.run_advanced_attack",
        "--run-id", run_id,
        "--dataset", dataset,
        "--provider", provider,
        "--model", model,
        "--timeout", str(timeout),
        "--suite", "clean_twin_sup",
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


def synthesize(rounds: list[str], attack_runs: Path, out_dir: Path, twin_root: Path) -> None:
    print(f"\n{'='*70}\n>>> SYNTHESIZING K=3 CLEAN TWIN SUP WITH clean_twin_sup.py\n{'='*70}", flush=True)
    twin_paths = [str(twin_root / rid / "raw_runs.jsonl") for rid in rounds]

    cmd = [
        PYTHON_EXE,
        str(ADV_DIR / "analysis" / "clean_twin_sup.py"),
        "--twin-runs", *twin_paths,
        "--attack-runs", str(attack_runs),
        "--out", str(out_dir),
    ]
    res = subprocess.run(cmd, cwd=str(AI_BACKEND), env=ENV)
    if res.returncode == 0:
        print(f"[✓] Synthesis successful! Report at: {out_dir / 'clean_twin_sup_report.md'}", flush=True)
    else:
        print(f"[!] Synthesis error (code={res.returncode})", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Run Clean Twin SUP k=3 pipeline")
    parser.add_argument("--provider", default="ollama", choices=["ollama", "gemini", "deepseek", "openai", "anthropic", "zhipu"])
    parser.add_argument("--dataset", default=DATASET, help="Dataset twin (mặc định 100 ca P+Z; có thể dùng file con, vd chỉ P-U2 + Z)")
    parser.add_argument("--model", default="gemini-3.5-flash-lite", help="Tên model (vd: deepseek-flash, qwen2.5:7b, qwen3:8b)")
    parser.add_argument("--tag", default=None, help="Prefix tên model (vd: deepseek_flash, qwen25_7b)")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--attack-runs", type=Path, default=None, help="Path tới raw_runs.jsonl lượt attack r1 của model này")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--use-mock-rag", action="store_true", default=False)
    parser.add_argument("--synthesize-only", action="store_true", default=False)

    args = parser.parse_args()
    tag = args.tag or (_slugify(args.model) if args.provider in ("ollama", "deepseek") else None)

    mdir = MODELS_DIR / _slugify(args.model)
    twin_root = mdir / "clean_twin_sup"
    if tag:
        rounds = [f"{tag}_clean_twin_sup_r1", f"{tag}_clean_twin_sup_r2", f"{tag}_clean_twin_sup_r3"]
        default_attack = mdir / "attack_advanced" / f"{tag}_adv_r1" / "raw_runs.jsonl"
        default_out = twin_root / f"out_clean_twin_sup_{tag}"
    else:
        rounds = ["clean_twin_sup_r1", "clean_twin_sup_r2", "clean_twin_sup_r3"]
        default_attack = mdir / "attack_advanced" / "advanced_benchmark_r1" / "raw_runs.jsonl"
        default_out = twin_root / "out_clean_twin_sup"

    # Không ghi đè kết quả đã có
    for rid in rounds:
        if (twin_root / rid / "raw_runs.jsonl").exists() and not args.synthesize_only:
            print(f"[STOP] Đã tồn tại {twin_root / rid}. Đổi --tag hoặc dời thư mục cũ trước khi chạy lại.", flush=True)
            sys.exit(1)

    attack_runs = args.attack_runs or default_attack
    out_dir = args.out or default_out

    print(f"Launching K=3 Clean Twin SUP: provider={args.provider}, model={args.model}, rounds={rounds}", flush=True)
    if not args.synthesize_only:
        for rid in rounds:
            ok = run_round(
                run_id=rid,
                provider=args.provider,
                model=args.model,
                timeout=args.timeout,
                limit=args.limit,
                use_mock_rag=args.use_mock_rag,
                dataset=args.dataset,
            )
            if not ok:
                print(f"[!] Pipeline halted due to error in {rid}.", flush=True)
                sys.exit(1)

    synthesize(rounds=rounds, attack_runs=attack_runs, out_dir=out_dir, twin_root=twin_root)
    print("\n[✓] ALL K=3 CLEAN TWIN SUP RUNS AND SYNTHESIS COMPLETED!", flush=True)


if __name__ == "__main__":
    main()
