#!/usr/bin/env python3
"""
Orchestrator & Synthesizer script for Benign Benchmark k=3:
- Runs 3 rounds (r1, r2, r3) of run_benign.py for any provider/model/config
- Runs BenignEvaluatorV2 on each round to collect full V2 metrics
- Synthesizes k=3 Mean +/- Std for Benign Utility (BU / ba_overall) and V2 metrics
Outputs:
- benchmarkv2_refined/models/<model>/benign/k3_benign_summary_<tag>_<config>.json
- benchmarkv2_refined/models/<model>/benign/K3_BENIGN_REPORT_<tag>_<config>.md
"""
from __future__ import annotations

import argparse
import json
import statistics
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
AI_BACKEND = Path(__file__).resolve().parents[3]
MODELS_DIR = AI_BACKEND / "benchmarkv2_refined" / "models"
# Kết quả ghi vào models/<model>/benign (gán lại trong main theo --model)
RESULTS_ROOT = MODELS_DIR
DATASET = AI_BACKEND / "benchmarkv2_refined" / "framework" / "benign" / "data" / "benign_v2_testcases.json"


def _slugify(model_name: str) -> str:
    return (
        model_name.strip()
        .replace(":", "_")
        .replace("/", "_")
        .replace("-", "_")
        .replace(".", "_")
    )


def _mean_std(vals: list[float]) -> tuple[float, float]:
    if not vals:
        return 0.0, 0.0
    m = statistics.mean(vals)
    s = statistics.stdev(vals) if len(vals) > 1 else 0.0
    return m, s


def run_round(
    out_dir: Path,
    config: str,
    provider: str,
    model: str,
    timeout: float,
    dataset: Path,
    limit: int | None,
    mock_rag: bool,
    defense: str = "none",
) -> bool:
    print(f"\n{'='*70}\n>>> START BENIGN ROUND: {out_dir.name} (provider={provider}, model={model})\n{'='*70}", flush=True)
    cmd = [
        PYTHON_EXE, "-m", "benchmarkv2_refined.framework.benign.runner.run_benign",
        "--config", config,
        "--dataset", str(dataset),
        "--output", str(out_dir),
        "--provider", provider,
        "--model", model,
        "--timeout", str(timeout),
        "--defense", defense,
    ]
    if limit is not None:
        cmd.extend(["--limit", str(limit)])
    if mock_rag:
        cmd.append("--mock-rag")

    t0 = time.time()
    res = subprocess.run(cmd, cwd=str(AI_BACKEND))
    elapsed = time.time() - t0
    if res.returncode != 0:
        print(f"[!] Error running {out_dir.name} (code={res.returncode}, elapsed={elapsed:.1f}s)", flush=True)
        return False

    # Evaluate V2 metrics per round
    raw_path = out_dir / "raw_runs.jsonl"
    eval_v2_path = out_dir / "eval_v2.json"
    eval_cmd = [
        PYTHON_EXE, "-m", "benchmarkv2_refined.framework.benign.evaluator.evaluate_benign_v2",
        "--runs", str(raw_path),
        "--dataset", str(dataset),
        "--output", str(eval_v2_path),
    ]
    subprocess.run(eval_cmd, cwd=str(AI_BACKEND))
    print(f"[✓] Finished {out_dir.name} in {elapsed/60:.1f} minutes", flush=True)
    return True


def synthesize_k3(round_dirs: list[Path], tag: str, config: str, model: str, provider: str) -> None:
    summaries = []
    v2_evals = []
    for d in round_dirs:
        s_path = d / "summary.json"
        if not s_path.exists():
            raise FileNotFoundError(f"Thiếu {s_path}")
        summaries.append(json.loads(s_path.read_text(encoding="utf-8")))
        e_path = d / "eval_v2.json"
        if e_path.exists():
            v2_evals.append(json.loads(e_path.read_text(encoding="utf-8")))

    bu_vals = [float(s.get("ba_overall", 0.0)) for s in summaries]
    bu_prot_vals = [float(s.get("ba_protective_action", 0.0)) for s in summaries]
    bu_safe_vals = [float(s.get("ba_safe_or_noise", 0.0)) for s in summaries]
    lat_vals = [float(s.get("avg_latency_ms", 0.0)) for s in summaries]

    bu_mean, bu_std = _mean_std(bu_vals)
    bu_prot_mean, bu_prot_std = _mean_std(bu_prot_vals)
    bu_safe_mean, bu_safe_std = _mean_std(bu_safe_vals)
    lat_mean, _ = _mean_std(lat_vals)

    v2_agg = {}
    if len(v2_evals) == len(round_dirs):
        for key in (
            "metric_1_classification_accuracy",
            "metric_2_safety_reasoning_score",
            "metric_3_action_compliance",
            "metric_5_execution_validity",
            "metric_6_outcome_and_safety",
            "protocol_coverage_avg",
        ):
            m, s = _mean_std([float(e.get(key, 0.0)) for e in v2_evals])
            v2_agg[key] = {"mean": m, "std": s, "rounds": [e.get(key, 0.0) for e in v2_evals]}
        v2_agg["critical_violations_total"] = sum(int(e.get("metric_4_critical_violations", 0)) for e in v2_evals)
        v2_agg["major_violations_total"] = sum(int(e.get("metric_4_major_violations", 0)) for e in v2_evals)
        v2_agg["minor_violations_total"] = sum(int(e.get("metric_4_minor_violations", 0)) for e in v2_evals)

    out_summary = {
        "tag": tag,
        "config": config,
        "provider": provider,
        "model": model,
        "k": len(round_dirs),
        "ba_overall": bu_mean,
        "ba_overall_std": bu_std,
        "ba_overall_rounds": bu_vals,
        "ba_protective_mean": bu_prot_mean,
        "ba_protective_std": bu_prot_std,
        "ba_safe_mean": bu_safe_mean,
        "ba_safe_std": bu_safe_std,
        "avg_latency_ms": round(lat_mean, 1),
        "v2_metrics": v2_agg,
        "round_dirs": [str(d) for d in round_dirs],
    }

    out_json = RESULTS_ROOT / f"k3_benign_summary_{tag}_{config}.json"
    out_md = RESULTS_ROOT / f"K3_BENIGN_REPORT_{tag}_{config}.md"
    out_json.write_text(json.dumps(out_summary, indent=2, ensure_ascii=False), encoding="utf-8")

    md = [
        f"# BÁO CÁO BENIGN BENCHMARK K={len(round_dirs)} ({model} | {config})",
        "",
        f"> **Provider:** `{provider}` | **Model:** `{model}` | **Config:** `{config}`",
        "",
        "| Chỉ số (Metric) | r1 | r2 | r3 | **Mean** | **Std** |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
        f"| **Benign Utility / Accuracy (BU)** | {bu_vals[0]*100:.2f}% | {bu_vals[1]*100:.2f}% | {bu_vals[2]*100:.2f}% | **{bu_mean*100:.2f}%** | ± {bu_std*100:.2f}% |"
        if len(bu_vals) == 3
        else f"| **Benign Utility / Accuracy (BU)** | — | — | — | **{bu_mean*100:.2f}%** | ± {bu_std*100:.2f}% |",
        f"| **BU (Nhóm cần hành động bảo vệ)** | — | — | — | **{bu_prot_mean*100:.2f}%** | ± {bu_prot_std*100:.2f}% |",
        f"| **BU (Nhóm an toàn / skip đúng)** | — | — | — | **{bu_safe_mean*100:.2f}%** | ± {bu_safe_std*100:.2f}% |",
    ]
    if v2_agg:
        m3 = v2_agg["metric_3_action_compliance"]
        m1 = v2_agg["metric_1_classification_accuracy"]
        m6 = v2_agg["metric_6_outcome_and_safety"]
        md.extend([
            f"| **Action Compliance (V2)** | — | — | — | **{m3['mean']*100:.2f}%** | ± {m3['std']*100:.2f}% |",
            f"| **Classification Accuracy (V2)** | — | — | — | **{m1['mean']*100:.2f}%** | ± {m1['std']*100:.2f}% |",
            f"| **Outcome & Safety (V2)** | — | — | — | **{m6['mean']*100:.2f}%** | ± {m6['std']*100:.2f}% |",
            f"| **Safety Violations (Crit/Maj/Min tổng 3 lượt)** | — | — | — | {v2_agg['critical_violations_total']} / {v2_agg['major_violations_total']} / {v2_agg['minor_violations_total']} | — |",
        ])
    md.append("")
    md.append(f"- Dùng file `{out_json}` cho tham số `--benign-summary` khi chạy `run_advanced_attack_k3_pipeline.py` để tính chính xác `Delta U = BU - UA`.")

    out_md.write_text("\n".join(md), encoding="utf-8")
    print(f"[✓] Đã lưu Benign k=3 summary tại: {out_json}")
    print(f"[✓] Đã lưu Benign k=3 report tại:  {out_md}")
    print(f">>> BU (Mean ± Std) = {bu_mean*100:.2f}% ± {bu_std*100:.2f}% (giá trị truyền --benign-baseline: {bu_mean:.4f})")


def main():
    parser = argparse.ArgumentParser(description="Run Benign Benchmark k=3 pipeline")
    parser.add_argument("--provider", default="ollama", choices=["ollama", "gemini", "deepseek", "openai", "anthropic", "zhipu"])
    parser.add_argument("--model", required=True, help="Tên model (vd: deepseek-flash, qwen2.5:7b, qwen3:8b)")
    parser.add_argument("--tag", default=None, help="Tên ngắn đặt thư mục output (mặc định tự sinh từ --model)")
    parser.add_argument("--config", default="with_conf_reflect", choices=["with_conf_reflect", "no_conf_reflect"])
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--mock-rag", action="store_true", default=False)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--synthesize-only", action="store_true", default=False)
    parser.add_argument("--defense", default="none", choices=["none", "prompt", "guard", "full"],
                        help="Phòng thủ Sensor-Grounded Response. Kết quả ghi vào benign_def_<mode>/, không đụng bản gốc")

    args = parser.parse_args()
    global RESULTS_ROOT
    sfx = "" if args.defense == "none" else f"_def_{args.defense}"
    RESULTS_ROOT = MODELS_DIR / _slugify(args.model) / f"benign{sfx}"
    tag = args.tag or _slugify(args.model)
    round_dirs = [RESULTS_ROOT / f"{tag}_{args.config}_r{i}{sfx}" for i in range(1, args.k + 1)]

    if not args.synthesize_only:
        for d in round_dirs:
            ok = run_round(
                out_dir=d,
                config=args.config,
                provider=args.provider,
                model=args.model,
                timeout=args.timeout,
                dataset=args.dataset,
                limit=args.limit,
                mock_rag=args.mock_rag,
                defense=args.defense,
            )
            if not ok:
                sys.exit(1)

    synthesize_k3(round_dirs, tag=tag + sfx, config=args.config, model=args.model, provider=args.provider)


if __name__ == "__main__":
    main()
