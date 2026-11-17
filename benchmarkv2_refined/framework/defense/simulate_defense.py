#!/usr/bin/env python3
"""
framework/defense/simulate_defense.py
-------------------------------------
Replay OFFLINE lớp SensorGuard (sensor_guard.py) trên raw_runs.jsonl đã có, rồi chấm lại bằng evaluator chuẩn
(GT v2.2.0, STRICT). Không gọi LLM, không chạy lại agent: guard là hậu xử lý deterministic trên đầu ra cuối
của agent + operational_context của testcase, nên replay cho đúng kết quả nếu guard được triển khai thật.

Chạy (từ benchmarkv2_refined/):
  python framework/defense/simulate_defense.py                 # replay trên run agent gốc
  python framework/defense/simulate_defense.py --source prompt  # replay trên run --defense prompt => kết quả "full"
Output: reports/defense/sensor_guard_simulation[_<source>].{md,json}
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                                   # benchmarkv2_refined
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "framework" / "ground_truth"))
import sensor_guard as G                                  # noqa: E402
from evaluate_advanced_attack_v2 import GT, eval_case as eval_attack, summarize  # noqa: E402
import evaluate_benign_strict as EB                       # noqa: E402

M = ROOT / "models"
ATTACK = {
    "Gemini": [M / "gemini_3_5_flash_lite/attack_advanced/advanced_benchmark_r1",
               M / "gemini_3_5_flash_lite/attack_advanced/advanced_benchmark_r2",
               M / "gemini_3_5_flash_lite/attack_advanced/advanced_benchmark_r3"],
    "GPT-5.6": [M / "gpt_5_6_luna/attack_advanced/gpt_5.6_luna_adv_r1"],
    "GPT-6": [M / "gpt_6_luna/attack_advanced/gpt_6_luna_adv_r1", M / "gpt_6_luna/attack_advanced/gpt_6_luna_adv_r2"],
    "Haiku": [M / "claude_haiku_5_5/attack_advanced/haiku_5_5_adv_r1"],
    "DeepSeek": [M / "deepseek_flash/attack_advanced/deepseek_flash_adv_r1"],
    "GLM": [M / "glm_5_3_flash/attack_advanced/glm_5_3_flash_adv_r1"],
}
BENIGN = {
    "Gemini": M / "gemini_3_5_flash_lite/benign/with_conf_reflect",
    "GPT-5.6": M / "gpt_6_luna/benign/gpt_6_luna_with_conf_reflect_r1",     # BU của GPT-6 dùng chung cho GPT-5.6
    "GPT-6": M / "gpt_6_luna/benign/gpt_6_luna_with_conf_reflect_r1",
    "Haiku": M / "claude_haiku_5_5/benign/haiku_5_5_with_conf_reflect_r1",
    "DeepSeek": M / "deepseek_flash/benign/deepseek_flash_with_conf_reflect_r1",
    "GLM": M / "glm_5_3_flash/benign/glm_5_3_flash_with_conf_reflect_r1",
}
VARIANTS = {"Gốc": dict(veto=False, floor=False), "D2 veto": dict(veto=True, floor=False),
            "D1 floor": dict(veto=False, floor=True), "D1+D2": dict(veto=True, floor=True)}


def load(p: Path):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def guarded(rec, payload, **kw):
    traj = rec.get("trajectory") or []
    acts = [s for s in traj if s.get("tool") in G.ACTION_TOOLS]
    if rec.get("run_status", "OK") != "OK":
        return rec, []
    new, log = G.apply(payload, acts, **kw)
    r = dict(rec)
    r["trajectory"] = [s for s in traj if s.get("tool") not in G.ACTION_TOOLS] + new
    return r, log


SLUG = {"Gemini": "gemini_3_5_flash_lite", "GPT-5.6": "gpt_5_6_luna", "GPT-6": "gpt_6_luna",
        "Haiku": "claude_haiku_5_5", "DeepSeek": "deepseek_flash", "GLM": "glm_5_3_flash"}


def source_runs(source: str):
    """Run của agent đã bật --defense <source>: mọi thư mục *_def_<source> có raw_runs.jsonl."""
    atk, ben = {}, {}
    for model, slug in SLUG.items():
        a = sorted(p.parent for p in (M / slug / f"attack_advanced_def_{source}").glob("*/raw_runs.jsonl"))
        b = sorted(p.parent for p in (M / slug / f"benign_def_{source}").glob("*/raw_runs.jsonl"))
        if a and b:
            atk[model], ben[model] = a, b[0]
    return atk, ben


def main():
    global ATTACK, BENIGN
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="none", help="none = run agent gốc; prompt = run đã bật --defense prompt")
    a = ap.parse_args()
    if a.source != "none":
        ATTACK, BENIGN = source_runs(a.source)
        if not ATTACK:
            sys.exit(f"Chưa có run nào ở attack_advanced_def_{a.source}/ và benign_def_{a.source}/")
    gt = GT(ROOT / "framework/ground_truth/ground_truth_v2.json")
    atk_tcs = {t["testcase_id"]: t for t in json.loads((ROOT / "framework/attack_advanced/data/advanced_attack_testcases.json").read_text(encoding="utf-8"))}
    ben_tcs = {t["test_id"]: t for t in json.loads((ROOT / "framework/benign/data/benign_v2_testcases.json").read_text(encoding="utf-8"))}

    res, fired = {}, Counter()
    for model, runs in ATTACK.items():
        res[model] = {}
        for vname, kw in VARIANTS.items():
            per_run = []
            for rd in runs:
                rows = []
                for rec in load(rd / "raw_runs.jsonl"):
                    tc = atk_tcs.get(rec["testcase_id"])
                    if not tc or tc.get("track") != "A":
                        continue
                    r2, log = guarded(rec, tc["payload"], **kw)
                    if vname == "D1+D2" and log:
                        fired[(model, "attack", tc["category"], log[0].split(":")[0].split(" (")[0])] += 1
                    rows.append(eval_attack(gt, tc, r2, "STRICT"))
                per_run.append(summarize(rows, 0.0))
            # benign
            brows = []
            for rec in load(BENIGN[model] / "raw_runs.jsonl"):
                tc = ben_tcs.get(rec.get("test_id") or rec.get("testcase_id"))
                if not tc:
                    continue
                r2, log = guarded(rec, tc["payload"], **kw)
                if vname == "D1+D2" and log:
                    fired[(model, "benign", tc["severity"], log[0].split(":")[0].split(" (")[0])] += 1
                brows.append(EB.eval_case(gt, tc, r2, "STRICT"))
            bu = sum(r["correct"] for r in brows) / max(1, len(brows))
            mean = lambda f: sum(f(s) for s in per_run) / len(per_run)
            res[model][vname] = {
                "BU": bu,
                "ASR": mean(lambda s: s["asr_valid"]["rate"]),
                "SUP": mean(lambda s: s["by_category"]["SUP"]["rate"]),
                "DH-A": mean(lambda s: s["by_category"]["DH-A"]["rate"]),
                "DH-S": mean(lambda s: s["by_category"]["DH-S"]["rate"]),
                "UA": mean(lambda s: s["ua"]["rate"]),
                "MHR": mean(lambda s: s["mhr"]["rate"]),
                "benign_wrong_ids": [r["test_id"] for r in brows if not r["correct"]],
            }

    out = ROOT / "reports" / "defense"
    out.mkdir(parents=True, exist_ok=True)
    tag = "" if a.source == "none" else f"_{a.source}"
    (out / f"sensor_guard_simulation{tag}.json").write_text(json.dumps(
        {"results": res, "fired": {" | ".join(k): v for k, v in fired.items()}}, ensure_ascii=False, indent=1), encoding="utf-8")

    pct = lambda x: f"{100*x:.1f}"
    L = [f"# Mô phỏng offline SensorGuard (GT v2.2.0), nguồn run: {a.source}", "",
         "Hàng 'Gốc' = đúng số của run nguồn; 'D1+D2' = khi bật guard (với nguồn prompt, đây là cấu hình full).", "",
         "| Model | Biến thể | BU | ASR | SUP | DH-A | DH-S | UA | MHR |", "| :-- | :-- | :-: | :-: | :-: | :-: | :-: | :-: | :-: |"]
    for model, vs in res.items():
        for v, d in vs.items():
            L.append(f"| {model} | {v} | {pct(d['BU'])} | {pct(d['ASR'])} | {pct(d['SUP'])} | {pct(d['DH-A'])} | {pct(d['DH-S'])} | {pct(d['UA'])} | {pct(d['MHR'])} |")
    L += ["", "## Guard can thiệp (D1+D2)", "", "| Model | Bộ | Nhóm | Can thiệp | Số lượt |", "| :-- | :-- | :-- | :-- | :-: |"]
    for k, v in sorted(fired.items()):
        L.append(f"| {' | '.join(k)} | {v} |")
    (out / f"sensor_guard_simulation{tag}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
