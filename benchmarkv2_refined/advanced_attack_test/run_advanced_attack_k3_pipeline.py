#!/usr/bin/env python3
"""
Orchestrator script to execute Advanced Attack Benchmark k=3:
- r1: advanced_benchmark_full (ALREADY DONE, 285 cases)
- r2: advanced_benchmark_r2 (285 cases)
- r3: advanced_benchmark_r3 (285 cases)
- Synthesize: synthesize_attack_k3.py
"""
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
AI_BACKEND = Path(__file__).resolve().parent

DATASET = "benchmarkv2_refined/advanced_attack_test/data/advanced_attack_testcases.json"
ROUNDS = ["advanced_benchmark_r2", "advanced_benchmark_r3"]

ENV = os.environ.copy()
ENV["PYTHONIOENCODING"] = "utf-8"

def run_round(run_id: str):
    print(f"\n{'='*70}\n>>> START ADVANCED ATTACK ROUND: {run_id} (285 testcases)\n{'='*70}", flush=True)
    cmd = [
        PYTHON_EXE, "-m", "benchmarkv2_refined.advanced_attack_test.runner.run_advanced_attack",
        "--run-id", run_id,
        "--dataset", DATASET
    ]
    t0 = time.time()
    res = subprocess.run(cmd, cwd=str(AI_BACKEND), env=ENV)
    elapsed = time.time() - t0
    if res.returncode != 0:
        print(f"[!] Error running {run_id} (code={res.returncode}, elapsed={elapsed:.1f}s)", flush=True)
        return False
    print(f"[✓] Finished {run_id} in {elapsed/60:.1f} minutes", flush=True)
    return True

def synthesize():
    print(f"\n{'='*70}\n>>> SYNTHESIZING K=3 ADVANCED ATTACKS\n{'='*70}", flush=True)
    cmd = [PYTHON_EXE, "synthesize_attack_k3.py"]
    res = subprocess.run(cmd, cwd=str(AI_BACKEND), env=ENV)
    if res.returncode == 0:
        print("[✓] Synthesis successful! Report at: benchmarkv2_refined/advanced_attack_test/runs/K3_ATTACK_SYNTHESIS_REPORT.md", flush=True)
    else:
        print(f"[!] Synthesis error (code={res.returncode})", flush=True)

def main():
    print("Launching K=3 Advanced Attack Benchmark (Round 2 and Round 3, 285 cases per round)...", flush=True)
    for rid in ROUNDS:
        ok = run_round(rid)
        if not ok:
            print(f"[!] Pipeline halted due to error in {rid}.", flush=True)
            sys.exit(1)
    
    synthesize()
    print("\n[✓] ALL K=3 ADVANCED ATTACK RUNS AND SYNTHESIS COMPLETED!", flush=True)

if __name__ == "__main__":
    main()
