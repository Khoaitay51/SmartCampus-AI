#!/usr/bin/env python3
"""
framework/defense/sweep_guard.py
--------------------------------
Replay OFFLINE (không gọi LLM) để kiểm tra độ khách quan của SensorGuard:

  1. Tách ASR thành SUP và phần còn lại (DH-A + DH-S + DS), vì guard bảo đảm SUP -> 0 gần như theo định nghĩa.
  2. Quét ngưỡng (nhân tất cả ngưỡng với 0.8 ... 1.2) và xem ASR / BU / báo động giả có ổn định không.
  3. So guard D1+D2 với baseline tầm thường "always-alert" (có nguy hiểm theo cảm biến thì thay bằng alert).
  4. Báo động giả: số ca benign Normal/Anomaly mà guard can thiệp.

Chạy (từ benchmarkv2_refined/):  python framework/defense/sweep_guard.py
Output: reports/defense/guard_robustness.{md,json}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import simulate_defense as SD                                   # noqa: E402
from simulate_defense import ROOT, GT, eval_attack, summarize, EB, load  # noqa: E402

sys.path.insert(0, str(HERE.parents[2]))
import app.safety.sensor_guard as AG                            # noqa: E402  (module gốc: patch hằng số ở đây)

THRESH = ["TEMP_HAZARD", "TEMP_CRITICAL", "CO2_HAZARD", "SMOKE_HAZARD", "SMOKE_CRITICAL",
          "TEMP_ELEVATED", "CO2_ELEVATED", "SMOKE_ELEVATED"]
BASE = {k: getattr(AG, k) for k in THRESH}
SCALES = [0.8, 0.9, 1.0, 1.1, 1.2]
NON_SUP = ("DH-A", "DH-S", "DS")


def set_scale(s: float) -> None:
    for k, v in BASE.items():
        setattr(AG, k, v * s)


def always_alert(rec, payload):
    """Baseline tầm thường: có nguy hiểm theo cảm biến -> bỏ hết hành động của agent, chỉ gửi alert."""
    traj = rec.get("trajectory") or []
    if rec.get("run_status", "OK") != "OK":
        return rec, False
    sens = AG.read_sensors(payload)
    hz = AG.hazards(sens)
    if not any(hz.values()):
        return rec, False
    r = dict(rec)
    room_id = (payload.get("event") or {}).get("room_id")
    r["trajectory"] = [s for s in traj if s.get("tool") not in AG.ACTION_TOOLS] + [AG.floor_action(room_id, sens, hz)]
    return r, True


def run_variant(model, variant, gt, atk_tcs, ben_tcs):
    """variant: 'none' | 'D1' | 'D2' | 'D1+D2' | 'always'. Trả số liệu gộp qua các run của model."""
    kw = {"none": dict(veto=False, floor=False), "D1": dict(veto=False, floor=True),
          "D2": dict(veto=True, floor=False), "D1+D2": dict(veto=True, floor=True)}.get(variant)
    cnt = {c: [0, 0] for c in ("SUP", "DH-A", "DH-S", "DS")}
    nrun = 0
    for rd in SD.ATTACK[model]:
        rows = []
        for rec in load(rd / "raw_runs.jsonl"):
            tc = atk_tcs.get(rec["testcase_id"])
            if not tc or tc.get("track") != "A":
                continue
            r2 = always_alert(rec, tc["payload"])[0] if variant == "always" else SD.guarded(rec, tc["payload"], **kw)[0]
            rows.append(eval_attack(gt, tc, r2, "STRICT"))
        s = summarize(rows, 0.0)
        for c in cnt:
            cnt[c][0] += s["by_category"][c]["count"]
            cnt[c][1] += s["by_category"][c]["total"]
        nrun += 1
    brows, fa, normal_anom = [], 0, 0
    for rec in load(SD.BENIGN[model] / "raw_runs.jsonl"):
        tc = ben_tcs.get(rec.get("test_id") or rec.get("testcase_id"))
        if not tc:
            continue
        if variant == "always":
            r2, fired = always_alert(rec, tc["payload"])
        else:
            r2, log = SD.guarded(rec, tc["payload"], **kw)
            fired = bool(log)
        if tc["severity"] in ("Normal", "Anomaly"):
            normal_anom += 1
            fa += int(fired)
        brows.append(EB.eval_case(gt, tc, r2, "STRICT"))
    bu = sum(r["correct"] for r in brows) / max(1, len(brows))
    tot = lambda cs: sum(cnt[c][0] for c in cs) / max(1, sum(cnt[c][1] for c in cs))
    return {"BU": bu, "ASR": tot(cnt), "SUP": tot(["SUP"]), "nonSUP": tot(NON_SUP),
            "DH-A": tot(["DH-A"]), "false_alarm": fa, "false_alarm_den": normal_anom}


def main():
    gt = GT(ROOT / "framework/ground_truth/ground_truth_v2.json")
    atk_tcs = {t["testcase_id"]: t for t in json.loads(
        (ROOT / "framework/attack_advanced/data/advanced_attack_testcases.json").read_text(encoding="utf-8"))}
    ben_tcs = {t["test_id"]: t for t in json.loads(
        (ROOT / "framework/benign/data/benign_v2_testcases.json").read_text(encoding="utf-8"))}
    p = lambda x: f"{100 * x:.1f}"
    out = {"at_scale_1": {}, "sweep": {}}
    L = ["# Độ khách quan của SensorGuard: replay offline (không gọi LLM)", "",
         "ASR = SUP + phần còn lại (DH-A, DH-S, DS gộp, gọi là non-SUP). FA = số ca benign Normal/Anomaly mà guard can thiệp "
         "(báo động giả; mẫu số 60).", "",
         "## 1. Tách ASR và so với baseline tầm thường (ngưỡng gốc)", "",
         "| Model | Biến thể | BU | ASR | SUP | non-SUP | DH-A | FA/60 |", "| :-- | :-- | --: | --: | --: | --: | --: | --: |"]
    set_scale(1.0)
    for model in SD.ATTACK:
        out["at_scale_1"][model] = {}
        for v, label in [("none", "Gốc"), ("D1+D2", "Guard D1+D2"), ("always", "Always-alert (tầm thường)")]:
            r = run_variant(model, v, gt, atk_tcs, ben_tcs)
            out["at_scale_1"][model][v] = r
            L.append(f"| {model} | {label} | {p(r['BU'])} | {p(r['ASR'])} | {p(r['SUP'])} | {p(r['nonSUP'])} | "
                     f"{p(r['DH-A'])} | {r['false_alarm']} |")
    L += ["", "## 2. Quét ngưỡng (nhân mọi ngưỡng với hệ số), guard D1+D2", "",
          "| Model | Hệ số | BU | ASR | SUP | non-SUP | FA/60 |", "| :-- | --: | --: | --: | --: | --: | --: |"]
    for model in SD.ATTACK:
        out["sweep"][model] = {}
        for s in SCALES:
            set_scale(s)
            r = run_variant(model, "D1+D2", gt, atk_tcs, ben_tcs)
            out["sweep"][model][str(s)] = r
            L.append(f"| {model} | {s} | {p(r['BU'])} | {p(r['ASR'])} | {p(r['SUP'])} | {p(r['nonSUP'])} | {r['false_alarm']} |")
    set_scale(1.0)
    d = ROOT / "reports" / "defense"
    d.mkdir(parents=True, exist_ok=True)
    (d / "guard_robustness.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "guard_robustness.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
