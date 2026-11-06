#!/usr/bin/env python3
"""
Orchestrator script to execute Clean Twin SUP k=3 rounds strictly following PLAN_CLEAN_TWIN_SUP_K3.md:
- r1: clean_twin_sup_r1 (100 cases)
- r2: clean_twin_sup_r2 (100 cases)
- r3: clean_twin_sup_r3 (100 cases)
- Synthesize: clean_twin_sup.py
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

DATASET = "benchmarkv2_refined/advanced_attack_test/data/clean_twin_sup_testcases.json"
ROUNDS = ["clean_twin_sup_r1", "clean_twin_sup_r2", "clean_twin_sup_r3"]

ENV = os.environ.copy()
ENV["PYTHONIOENCODING"] = "utf-8"

def run_round(run_id: str):
    print(f"\n{'='*70}\n>>> START CLEAN TWIN SUP ROUND: {run_id}\n{'='*70}", flush=True)
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
    print(f"\n{'='*70}\n>>> SYNTHESIZING K=3 CLEAN TWIN SUP WITH clean_twin_sup.py\n{'='*70}", flush=True)
    r1 = "benchmarkv2_refined/advanced_attack_test/runs/clean_twin_sup_r1/raw_runs.jsonl"
    r2 = "benchmarkv2_refined/advanced_attack_test/runs/clean_twin_sup_r2/raw_runs.jsonl"
    r3 = "benchmarkv2_refined/advanced_attack_test/runs/clean_twin_sup_r3/raw_runs.jsonl"
    
    cmd = [
        PYTHON_EXE, "benchmarkv2_refined/advanced_attack_test/analysis/clean_twin_sup.py",
        "--twin-runs", r1, r2, r3
    ]
    res = subprocess.run(cmd, cwd=str(AI_BACKEND), env=ENV)
    if res.returncode == 0:
        print("[✓] Synthesis successful! Report at: analysis/out_clean_twin_sup/clean_twin_sup_report.md", flush=True)
    else:
        print(f"[!] Synthesis error (code={res.returncode})", flush=True)

def main():
    print("Launching K=3 Clean Twin SUP (100 cases per round, total 300 runs)...", flush=True)
    for rid in ROUNDS:
        ok = run_round(rid)
        if not ok:
            print(f"[!] Pipeline halted due to error in {rid}.", flush=True)
            sys.exit(1)
    
    synthesize()
    print("\n[✓] ALL K=3 CLEAN TWIN SUP RUNS AND SYNTHESIS COMPLETED!", flush=True)

if __name__ == "__main__":
    main()
