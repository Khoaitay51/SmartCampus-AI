#!/usr/bin/env python3
"""
framework/defense/guard_burden.py
Đo gánh nặng cho admin khi chỉ bật SensorGuard (không đổi system prompt), replay offline trên run baseline.
Với mỗi model: số alert agent tự phát ra, số alert guard CHÈN THÊM (floor), số báo động giả
(floor ở ca benign nhóm Normal/Anomaly, tức không có hazard thật), và số hành động bị veto.
Chạy (từ benchmarkv2_refined/): python framework/defense/guard_burden.py
Output: reports/defense/guard_burden.{md,json}
"""
from __future__ import annotations
import json, sys
from collections import Counter
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import simulate_defense as S
G = S.G

def n_alerts(traj):
    return sum(1 for s in (traj or []) if s.get("tool") == "send_alert")

def main():
    atk_tcs = {t["testcase_id"]: t for t in json.loads((S.ROOT / "framework/attack_advanced/data/advanced_attack_testcases.json").read_text(encoding="utf-8"))}
    ben_tcs = {t["test_id"]: t for t in json.loads((S.ROOT / "framework/benign/data/benign_v2_testcases.json").read_text(encoding="utf-8"))}
    kw = dict(veto=True, floor=True)
    out = {}
    for model, runs in S.ATTACK.items():
        # benign
        b = Counter(); bsev = Counter()
        brecs = S.load(S.BENIGN[model] / "raw_runs.jsonl")
        for rec in brecs:
            tc = ben_tcs.get(rec.get("test_id") or rec.get("testcase_id"))
            if not tc: continue
            b["n"] += 1
            b["alerts_base"] += n_alerts(rec.get("trajectory"))
            r2, log = S.guarded(rec, tc["payload"], **kw)
            b["alerts_guard"] += n_alerts(r2.get("trajectory"))
            for l in log:
                if l.startswith("floor"):
                    b["floor"] += 1; bsev[tc["severity"]] += 1
                elif l.startswith("veto"):
                    b["veto"] += 1
        # attack Track A, tính trung bình theo run
        a = Counter(); asev = Counter(); nrun = 0
        for rd in runs:
            nrun += 1
            for rec in S.load(rd / "raw_runs.jsonl"):
                tc = atk_tcs.get(rec["testcase_id"])
                if not tc or tc.get("track") != "A": continue
                a["n"] += 1
                a["alerts_base"] += n_alerts(rec.get("trajectory"))
                r2, log = S.guarded(rec, tc["payload"], **kw)
                a["alerts_guard"] += n_alerts(r2.get("trajectory"))
                for l in log:
                    if l.startswith("floor"):
                        a["floor"] += 1; asev[tc["category"]] += 1
                    elif l.startswith("veto"):
                        a["veto"] += 1
        out[model] = {"benign": dict(b), "benign_floor_by_severity": dict(bsev),
                      "attack": {k: v / nrun for k, v in a.items()}, "attack_floor_by_cat": {k: v / nrun for k, v in asev.items()}, "runs": nrun}
    (S.ROOT / "reports/defense/guard_burden.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    L = ["# Gánh nặng cho admin khi chỉ bật SensorGuard (GT v2.2.0, replay offline trên run baseline)", "",
         "## Benign (100 ca, không có tấn công)", "",
         "| Model | Alert agent phát | Alert guard chèn thêm | Chèn ở ca Normal/Anomaly (báo giả) | Chèn ở ca Hazard/Emergency | Hành động bị veto |",
         "| :-- | :-: | :-: | :-: | :-: | :-: |"]
    for m, d in out.items():
        b, s = d["benign"], d["benign_floor_by_severity"]
        fake = s.get("Normal", 0) + s.get("Anomaly", 0)
        real = s.get("Hazard", 0) + s.get("Emergency", 0)
        L.append(f"| {m} | {b['alerts_base']} | {b.get('floor',0)} | {fake} | {real} | {b.get('veto',0)} |")
    L += ["", "## Attack Track A (254 ca/run, trung bình theo run)", "",
          "| Model | Alert agent phát | Alert guard chèn thêm | Chèn thêm / ca | Hành động bị veto |", "| :-- | :-: | :-: | :-: | :-: |"]
    for m, d in out.items():
        a = d["attack"]
        L.append(f"| {m} | {a['alerts_base']:.0f} | {a.get('floor',0):.0f} | {a.get('floor',0)/a['n']:.2f} | {a.get('veto',0):.0f} |")
    (S.ROOT / "reports/defense/guard_burden.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))

if __name__ == "__main__":
    main()
