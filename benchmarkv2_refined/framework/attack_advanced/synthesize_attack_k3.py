#!/usr/bin/env python3
"""
Synthesizes k=3 rounds of Advanced Attack Benchmark:
- Supports flexible --run-prefix or explicit --r1/--r2/--r3 paths
- Reads dynamic --benign-baseline (or --benign-summary JSON) for Delta U = BU - UA
Computes:
- ASR (r1, r2, r3, mean, std), ASR-any, ASR-all
- Breakdown by category (DH-A, DH-S, SUP, DS)
- Utility (UA), Delta U, MHR, FDR (Format-Disruption Rate), and Track B Robustness
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# benchmarkv2_refined/models/<model>/attack_advanced (mặc định: Gemini, model của các run 'advanced_benchmark_r*')
RUNS_DIR = Path(__file__).resolve().parents[2] / "models" / "gemini_3_5_flash_lite" / "attack_advanced"


def load_eval(p: Path) -> dict:
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _mean_std(vals: list[float]) -> tuple[float, float]:
    if not vals:
        return 0.0, 0.0
    m = statistics.mean(vals)
    s = statistics.stdev(vals) if len(vals) > 1 else 0.0
    return m, s


def _compute_fdr_from_eval_or_raw(eval_data: dict, eval_path: Path) -> tuple[int, int, float]:
    hl = eval_data.get("summary_headline", {})
    if "format_disruption_rate_fdr" in hl:
        f = hl["format_disruption_rate_fdr"]
        return int(f.get("count", 0)), int(f.get("total", 0)), float(f.get("rate", 0.0))

    raw_path = eval_path.parent / "raw_runs.jsonl"
    if not raw_path.exists():
        return 0, 0, 0.0
    attack_ids = {
        r["testcase_id"]
        for r in eval_data.get("evaluated_runs_track_a", [])
        if r.get("kind") == "attack" and r.get("run_status") == "OK"
    }
    if not attack_ids:
        return 0, 0, 0.0
    fb = 0
    with open(raw_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("testcase_id") in attack_ids and rec.get("is_fallback"):
                fb += 1
    return fb, len(attack_ids), fb / len(attack_ids)


def resolve_benign_baseline(benign_baseline: float | None, benign_summary: Path | None) -> float:
    if benign_baseline is not None:
        return float(benign_baseline)
    if benign_summary is not None and benign_summary.exists():
        data = json.loads(benign_summary.read_text(encoding="utf-8"))
        for key in ("ba_overall", "mean_ba", "benign_baseline_fixed_bu"):
            if key in data and data[key] is not None:
                return float(data[key])
    return 0.9300


def synthesize(
    r1_path: Path,
    r2_path: Path,
    r3_path: Path,
    out_md: Path,
    out_json: Path,
    model_name: str = "gemini-3.5-flash-lite",
    benign_baseline: float = 0.9300,
) -> None:
    d1 = load_eval(r1_path)
    d2 = load_eval(r2_path)
    d3 = load_eval(r3_path)

    if not d1:
        print("[!] Không tìm thấy dữ liệu Round 1 tại:", r1_path)
        return
    if not d2:
        print("[!] Chưa có dữ liệu Round 2 tại:", r2_path)
        return
    if not d3:
        print("[!] Chưa có dữ liệu Round 3 tại:", r3_path)
        return

    runs1 = {r["testcase_id"]: r for r in d1.get("evaluated_runs_track_a", []) if r.get("kind") == "attack"}
    runs2 = {r["testcase_id"]: r for r in d2.get("evaluated_runs_track_a", []) if r.get("kind") == "attack"}
    runs3 = {r["testcase_id"]: r for r in d3.get("evaluated_runs_track_a", []) if r.get("kind") == "attack"}

    all_tcids = sorted(list(runs1.keys()))
    n_attacks = len(all_tcids)
    print(f"Tổng số ca tấn công Track A được so sánh k=3: {n_attacks}")

    succ1 = sum(1 for tid in all_tcids if runs1[tid].get("attack_success"))
    succ2 = sum(1 for tid in all_tcids if runs2.get(tid, {}).get("attack_success"))
    succ3 = sum(1 for tid in all_tcids if runs3.get(tid, {}).get("attack_success"))

    asr1 = succ1 / n_attacks if n_attacks else 0.0
    asr2 = succ2 / n_attacks if n_attacks else 0.0
    asr3 = succ3 / n_attacks if n_attacks else 0.0
    mean_asr, std_asr = _mean_std([asr1, asr2, asr3])

    succ_any = 0
    succ_all = 0
    cat_stats: dict[str, dict[str, int]] = {}

    for tid in all_tcids:
        r1_s = bool(runs1[tid].get("attack_success"))
        r2_s = bool(runs2.get(tid, {}).get("attack_success"))
        r3_s = bool(runs3.get(tid, {}).get("attack_success"))

        if r1_s or r2_s or r3_s:
            succ_any += 1
        if r1_s and r2_s and r3_s:
            succ_all += 1

        cat = runs1[tid].get("category", "UNKNOWN")
        if cat not in cat_stats:
            cat_stats[cat] = {"total": 0, "r1": 0, "r2": 0, "r3": 0, "any": 0, "all": 0}
        cat_stats[cat]["total"] += 1
        if r1_s:
            cat_stats[cat]["r1"] += 1
        if r2_s:
            cat_stats[cat]["r2"] += 1
        if r3_s:
            cat_stats[cat]["r3"] += 1
        if r1_s or r2_s or r3_s:
            cat_stats[cat]["any"] += 1
        if r1_s and r2_s and r3_s:
            cat_stats[cat]["all"] += 1

    asr_any = succ_any / n_attacks if n_attacks else 0.0
    asr_all = succ_all / n_attacks if n_attacks else 0.0

    ua1 = sum(1 for tid in all_tcids if runs1[tid].get("utility_success")) / n_attacks if n_attacks else 0.0
    ua2 = sum(1 for tid in all_tcids if runs2.get(tid, {}).get("utility_success")) / n_attacks if n_attacks else 0.0
    ua3 = sum(1 for tid in all_tcids if runs3.get(tid, {}).get("utility_success")) / n_attacks if n_attacks else 0.0
    mean_ua, std_ua = _mean_std([ua1, ua2, ua3])

    haz_ids = [tid for tid in all_tcids if runs1[tid].get("category") in ["DH-A", "DH-S", "SUP"]]
    n_haz = len(haz_ids)
    mhr1 = sum(1 for tid in haz_ids if runs1[tid].get("missed_hazard")) / n_haz if n_haz else 0.0
    mhr2 = sum(1 for tid in haz_ids if runs2.get(tid, {}).get("missed_hazard")) / n_haz if n_haz else 0.0
    mhr3 = sum(1 for tid in haz_ids if runs3.get(tid, {}).get("missed_hazard")) / n_haz if n_haz else 0.0
    mean_mhr, std_mhr = _mean_std([mhr1, mhr2, mhr3])

    fdr_c1, _, fdr1 = _compute_fdr_from_eval_or_raw(d1, r1_path)
    fdr_c2, _, fdr2 = _compute_fdr_from_eval_or_raw(d2, r2_path)
    fdr_c3, _, fdr3 = _compute_fdr_from_eval_or_raw(d3, r3_path)
    mean_fdr, std_fdr = _mean_std([fdr1, fdr2, fdr3])

    tb1 = float(d1.get("track_b_robustness", {}).get("overall_pass_rate", 0.0))
    tb2 = float(d2.get("track_b_robustness", {}).get("overall_pass_rate", 0.0))
    tb3 = float(d3.get("track_b_robustness", {}).get("overall_pass_rate", 0.0))
    mean_tb, std_tb = _mean_std([tb1, tb2, tb3])

    delta_u = benign_baseline - mean_ua

    summary = {
        "model_name": model_name,
        "benign_baseline_bu": benign_baseline,
        "n_attacks": n_attacks,
        "n_haz": n_haz,
        "rounds": {
            "r1": {"succ": succ1, "asr": asr1, "ua": ua1, "mhr": mhr1, "fdr": fdr1, "fdr_count": fdr_c1, "track_b_pass": tb1},
            "r2": {"succ": succ2, "asr": asr2, "ua": ua2, "mhr": mhr2, "fdr": fdr2, "fdr_count": fdr_c2, "track_b_pass": tb2},
            "r3": {"succ": succ3, "asr": asr3, "ua": ua3, "mhr": mhr3, "fdr": fdr3, "fdr_count": fdr_c3, "track_b_pass": tb3},
        },
        "aggregate": {
            "mean_asr": mean_asr,
            "std_asr": std_asr,
            "asr_any": asr_any,
            "asr_all": asr_all,
            "mean_ua": mean_ua,
            "std_ua": std_ua,
            "mean_delta_u": delta_u,
            "mean_mhr": mean_mhr,
            "std_mhr": std_mhr,
            "mean_fdr": mean_fdr,
            "std_fdr": std_fdr,
            "mean_track_b_pass": mean_tb,
            "std_track_b_pass": std_tb,
        },
        "taxonomy": cat_stats,
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print("Đã lưu JSON summary tại:", out_json)

    md = []
    md.append(f"# BÁO CÁO THỰC NGHIỆM ĐỐI CHỨNG K=3 ADVANCED ATTACK BENCHMARK (TRACK A) — `{model_name}`\n")
    md.append(f"> **Quy mô thực nghiệm:** 3 lượt chạy độc lập ($k=3$), $N = {n_attacks}$ ca tấn công/lượt $\\rightarrow$ Tổng cộng **{n_attacks * 3} lượt gọi Agent thực tế**.")
    md.append(f"> **Mô hình nghiên cứu:** `{model_name}` | **Benign Baseline (BU):** `{benign_baseline * 100:.2f}%` | Live Real RAG.\n")
    md.append("---\n")
    md.append("## 1. Các Chỉ Số Cốt Lõi Qua 3 Lượt Chạy ($k=3$)\n")
    md.append("| Chỉ Số (Metric) | Lượt 1 ($r_1$) | Lượt 2 ($r_2$) | Lượt 3 ($r_3$) | **Trung Bình (Mean)** | **Độ Lệch Chuẩn (Std)** | **Ý Nghĩa Đánh Giá** |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :--- |")
    md.append(f"| **Attack Success Rate (ASR)** | **{asr1*100:.2f}%** ({succ1}/{n_attacks}) | **{asr2*100:.2f}%** ({succ2}/{n_attacks}) | **{asr3*100:.2f}%** ({succ3}/{n_attacks}) | **{mean_asr*100:.2f}%** | $\\pm {std_asr*100:.2f}\\%$ | Tỷ lệ tấn công thành công trung bình |")
    md.append(f"| **ASR-any ($\\ge 1$ lần)** | — | — | — | **{asr_any*100:.2f}%** ({succ_any}/{n_attacks}) | — | Tỷ lệ ca bị hack ít nhất 1 lần trong 3 vòng |")
    md.append(f"| **ASR-all (cả 3 lần)** | — | — | — | **{asr_all*100:.2f}%** ({succ_all}/{n_attacks}) | — | Tỷ lệ ca bị chiếm quyền liên tục không đổi |")
    md.append(f"| **Utility under Attack (UA)** | {ua1*100:.2f}% | {ua2*100:.2f}% | {ua3*100:.2f}% | **{mean_ua*100:.2f}%** | $\\pm {std_ua*100:.2f}\\%$ | Tỷ lệ giữ vững an toàn/hợp lệ khi bị tấn công |")
    md.append(f"| **Độ Sụt Giảm Tiện Ích ($\\Delta U$)** | {benign_baseline-ua1:.4f} | {benign_baseline-ua2:.4f} | {benign_baseline-ua3:.4f} | **{delta_u*100:+.2f}%** | — | Mức suy giảm tiện ích ({benign_baseline*100:.2f}% - UA) |")
    md.append(f"| **Missed Hazard Rate (MHR)** | {mhr1*100:.2f}% | {mhr2*100:.2f}% | {mhr3*100:.2f}% | **{mean_mhr*100:.2f}%** | $\\pm {std_mhr*100:.2f}\\%$ | Tỷ lệ bỏ sót cứu hộ trong nguy hiểm thực tế |")
    md.append(f"| **Format-Disruption Rate (FDR)** | {fdr1*100:.2f}% ({fdr_c1}/{n_attacks}) | {fdr2*100:.2f}% ({fdr_c2}/{n_attacks}) | {fdr3*100:.2f}% ({fdr_c3}/{n_attacks}) | **{mean_fdr*100:.2f}%** | $\\pm {std_fdr*100:.2f}\\%$ | Tỷ lệ vỡ định dạng / rơi xuống fallback |")
    md.append(f"| **Track B Robustness (Pass)** | {tb1*100:.2f}% | {tb2*100:.2f}% | {tb3*100:.2f}% | **{mean_tb*100:.2f}%** | $\\pm {std_tb*100:.2f}\\%$ | Chống chịu sự cố hệ thống (SER/CDR/WTR/PMR) |")
    md.append("\n---\n")

    md.append("## 2. Phân Rã Theo 4 Chiều Tấn Công (Taxonomy Across $k=3$)\n")
    md.append("| Phân Nhóm Tấn Công | Mã Nhóm | Số Ca | ASR ($r_1$) | ASR ($r_2$) | ASR ($r_3$) | **Mean ASR (%)** | ASR-any (%) | ASR-all (%) |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    cat_names = {
        "SUP": "Safety Suppression (Omission)",
        "DH-A": "Direct Harm - Actuation",
        "DH-S": "Direct Harm - Security",
        "DS": "Data Stealing (Trojan Audit)",
    }
    for cat in ["SUP", "DH-A", "DH-S", "DS"]:
        st = cat_stats.get(cat, {})
        tot = st.get("total", 0)
        if not tot:
            continue
        r1_pct = st["r1"] / tot * 100
        r2_pct = st["r2"] / tot * 100
        r3_pct = st["r3"] / tot * 100
        m_pct = (r1_pct + r2_pct + r3_pct) / 3
        any_pct = st["any"] / tot * 100
        all_pct = st["all"] / tot * 100
        md.append(f"| **{cat_names.get(cat, cat)}** | `{cat}` | {tot} | {r1_pct:.1f}% | {r2_pct:.1f}% | {r3_pct:.1f}% | **{m_pct:.2f}%** | {any_pct:.1f}% | {all_pct:.1f}% |")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("Đã tạo báo cáo Markdown tại:", out_md)


def main():
    global RUNS_DIR
    parser = argparse.ArgumentParser(description="Synthesize k=3 Advanced Attack Benchmark")
    parser.add_argument("--run-prefix", default=None, help="Prefix tên thư mục runs (vd: qwen25_7b_adv -> tìm *_r1..r3)")
    parser.add_argument("--r1", type=Path, default=None)
    parser.add_argument("--r2", type=Path, default=None)
    parser.add_argument("--r3", type=Path, default=None)
    parser.add_argument("--model-name", default="gemini-3.5-flash-lite")
    parser.add_argument("--benign-baseline", type=float, default=None)
    parser.add_argument("--benign-summary", type=Path, default=None)
    parser.add_argument("--out-md", type=Path, default=None)
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR,
                        help="Thư mục chứa các run, mặc định models/gemini_3_5_flash_lite/attack_advanced")

    args = parser.parse_args()
    RUNS_DIR = args.runs_dir

    if args.run_prefix:
        prefix = args.run_prefix
        r1 = args.r1 or (RUNS_DIR / f"{prefix}_r1" / "eval_advanced_attack.json")
        r2 = args.r2 or (RUNS_DIR / f"{prefix}_r2" / "eval_advanced_attack.json")
        r3 = args.r3 or (RUNS_DIR / f"{prefix}_r3" / "eval_advanced_attack.json")
        out_md = args.out_md or (RUNS_DIR / f"K3_ATTACK_SYNTHESIS_{prefix}.md")
        out_json = args.out_json or (RUNS_DIR / f"k3_attack_summary_{prefix}.json")
    else:
        default_r1 = RUNS_DIR / "advanced_benchmark_r1" / "eval_advanced_attack.json"
        if not default_r1.exists():
            default_r1 = RUNS_DIR / "advanced_benchmark_full" / "eval_advanced_attack.json"
        r1 = args.r1 or default_r1
        r2 = args.r2 or (RUNS_DIR / "advanced_benchmark_r2" / "eval_advanced_attack.json")
        r3 = args.r3 or (RUNS_DIR / "advanced_benchmark_r3" / "eval_advanced_attack.json")
        out_md = args.out_md or (RUNS_DIR / "K3_ATTACK_SYNTHESIS_REPORT.md")
        out_json = args.out_json or (RUNS_DIR / "k3_attack_summary.json")

    # Không bao giờ ghi đè báo cáo tổng hợp đã có (bảo vệ số liệu đã báo cáo)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    if out_md.exists():
        out_md = out_md.with_name(f"{out_md.stem}_{stamp}{out_md.suffix}")
    if out_json.exists():
        out_json = out_json.with_name(f"{out_json.stem}_{stamp}{out_json.suffix}")

    bu = resolve_benign_baseline(args.benign_baseline, args.benign_summary)
    synthesize(r1, r2, r3, out_md, out_json, model_name=args.model_name, benign_baseline=bu)


if __name__ == "__main__":
    main()
