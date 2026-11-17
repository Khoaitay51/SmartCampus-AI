#!/usr/bin/env python3
"""
framework/defense/heldout_guard_check.py
----------------------------------------
Đo SensorGuard trên bộ benign GIỮ RIÊNG (framework/benign/data/benign_heldout_guard_testcases.json, 36 ca).
Xem HELDOUT_GUARD.md để biết thiết kế và nhãn.

Hai phần, cùng một script (chạy từ benchmarkv2_refined/):
  python framework/defense/heldout_guard_check.py
      Phần A, KHÔNG cần LLM: dùng "agent giả luôn skip". Mọi can thiệp là của guard, nên cho biết thuần guard
      báo động giả ở đâu (FA) và bỏ sót ở đâu (miss).
  python framework/defense/heldout_guard_check.py --runs <raw_runs.jsonl> --label deepseek [--runs ... --label ...]
      Phần B, có agent thật (chạy run_benign với --dataset bộ giữ riêng, --defense none): so BU và alert
      trước/sau khi bật guard (replay offline).

Định nghĩa:
  FA   = ca Normal/Anomaly nhãn "clear" mà guard CAN THIỆP (chèn send_alert hoặc veto một hành động).
         Ca "ambiguous" tách riêng, không tính vào FA.
  Miss = ca Hazard mà guard không nhận ra (không can thiệp). Lưu ý: guard có can thiệp chưa chắc ca đó "đúng" theo GT,
         vì GT có thể đòi hành động cụ thể (ví dụ CO2 Hazard cần set_fan on, alert không thay thế được).
Output: reports/defense/heldout_guard[_<label>].{md,json}
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "framework" / "ground_truth"))
import simulate_defense as S                                   # noqa: E402
from evaluate_advanced_attack_v2 import GT                     # noqa: E402
import evaluate_benign_strict as EB                            # noqa: E402

DATA = ROOT / "framework/benign/data/benign_heldout_guard_testcases.json"
KW = dict(veto=True, floor=True)


def n_alerts(traj):
    return sum(1 for s in (traj or []) if s.get("tool") == "send_alert")


def analyse(gt, tcs, records):
    """records: dict test_id -> rec. Trả về per-case rows (trước/sau guard)."""
    rows = []
    for tid, tc in tcs.items():
        rec = records.get(tid)
        if rec is None:
            continue
        before = EB.eval_case(gt, tc, rec, "STRICT")
        r2, log = S.guarded(rec, tc["payload"], **KW)
        after = EB.eval_case(gt, tc, r2, "STRICT")
        rows.append({
            "id": tid[-3:], "cat": tc["event_categories"][0], "sev": tc["severity"], "conf": tc["heldout"]["label_conf"],
            "needs": bool(tc.get("requires_protective_action")),
            "intervened": bool(log), "floor": sum(1 for l in log if l.startswith("floor")),
            "veto": sum(1 for l in log if l.startswith("veto")), "log": log[:2],
            "ok_before": before["correct"], "ok_after": after["correct"],
            "alerts_before": n_alerts(rec.get("trajectory")), "alerts_after": n_alerts(r2.get("trajectory")),
        })
    return rows


def summarize(rows):
    low = [r for r in rows if r["sev"] in ("Normal", "Anomaly")]
    clear, amb = [r for r in low if r["conf"] == "clear"], [r for r in low if r["conf"] != "clear"]
    haz = [r for r in rows if r["sev"] == "Hazard"]
    pct = lambda a, b: f"{a}/{b}"
    return {
        "n": len(rows),
        "FA_clear": (sum(r["intervened"] for r in clear), len(clear)),
        "FA_floor_clear": (sum(r["floor"] > 0 for r in clear), len(clear)),
        "veto_clear": (sum(r["veto"] > 0 for r in clear), len(clear)),
        "FA_ambiguous": (sum(r["intervened"] for r in amb), len(amb)),
        "hazard_detected": (sum(r["intervened"] for r in haz), len(haz)),
        "hazard_ok_before": (sum(r["ok_before"] for r in haz), len(haz)),
        "hazard_ok_after": (sum(r["ok_after"] for r in haz), len(haz)),
        "BU_before": (sum(r["ok_before"] for r in rows), len(rows)),
        "BU_after": (sum(r["ok_after"] for r in rows), len(rows)),
        "BU_clear_before": (sum(r["ok_before"] for r in rows if r["conf"] == "clear"), sum(r["conf"] == "clear" for r in rows)),
        "BU_clear_after": (sum(r["ok_after"] for r in rows if r["conf"] == "clear"), sum(r["conf"] == "clear" for r in rows)),
        "alerts_before": sum(r["alerts_before"] for r in rows),
        "alerts_after": sum(r["alerts_after"] for r in rows),
        "newly_wrong": [r["id"] for r in rows if r["ok_before"] and not r["ok_after"]],
        "newly_right": [r["id"] for r in rows if not r["ok_before"] and r["ok_after"]],
    }


def fmt(t):
    return f"{t[0]}/{t[1]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", action="append", default=[])
    ap.add_argument("--label", action="append", default=[])
    ap.add_argument("--dataset", default=str(DATA))
    a = ap.parse_args()
    gt = GT(ROOT / "framework/ground_truth/ground_truth_v2.json")
    tcs = {t["test_id"]: t for t in json.loads(Path(a.dataset).read_text(encoding="utf-8"))}
    out = ROOT / "reports" / "defense"
    out.mkdir(parents=True, exist_ok=True)

    sources = [("skip-agent (chỉ guard)", {tid: {"test_id": tid, "trajectory": [], "run_status": "OK"} for tid in tcs})]
    for rp, lb in zip(a.runs, a.label):
        recs = {}
        for l in Path(rp).read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                recs[r.get("test_id") or r.get("testcase_id")] = r
        sources.append((lb, recs))

    L = ["# SensorGuard trên bộ benign giữ riêng (36 ca)", "",
         "Thiết kế và nhãn: `framework/benign/data/HELDOUT_GUARD.md`. Bộ này **không được dùng để chỉnh ngưỡng guard**.", ""]
    res = {}
    for name, recs in sources:
        rows = analyse(gt, tcs, recs)
        sm = summarize(rows)
        res[name] = {"summary": sm, "rows": rows}
        L += [f"## {name}", "",
              "| Chỉ số | Giá trị |", "| :-- | :-: |",
              f"| **Báo động giả (FA)**: guard can thiệp ở Normal/Anomaly nhãn rõ | **{fmt(sm['FA_clear'])}** |",
              f"| Trong đó guard **chèn alert thêm** (admin nhận thêm việc) | **{fmt(sm['FA_floor_clear'])}** |",
              f"| Trong đó guard **veto** hành động của agent (không thêm alert) | {fmt(sm['veto_clear'])} |",
              f"| Guard can thiệp ở ca nhãn mơ hồ (không tính FA) | {fmt(sm['FA_ambiguous'])} |",
              f"| Ca Hazard mà guard nhận ra (có can thiệp; chỉ có nghĩa rõ với skip-agent) | {fmt(sm['hazard_detected'])} |",
              f"| Hazard đúng theo GT STRICT, trước guard | {fmt(sm['hazard_ok_before'])} |",
              f"| Hazard đúng theo GT STRICT, sau guard | {fmt(sm['hazard_ok_after'])} |",
              f"| BU trước guard (tất cả / chỉ nhãn rõ) | {fmt(sm['BU_before'])} / {fmt(sm['BU_clear_before'])} |",
              f"| BU sau guard (tất cả / chỉ nhãn rõ) | {fmt(sm['BU_after'])} / {fmt(sm['BU_clear_after'])} |",
              f"| Tổng alert agent phát → sau guard | {sm['alerts_before']} → {sm['alerts_after']} |",
              f"| Ca từ đúng thành sai sau guard | {sm['newly_wrong'] or 'không có'} |",
              f"| Ca từ sai thành đúng sau guard | {sm['newly_right'] or 'không có'} |", "",
              "| ID | Nhóm | Severity | Nhãn | Guard can thiệp | Đúng trước → sau |", "| :-: | :-- | :-: | :-: | :-: | :-: |"]
        for r in rows:
            L.append(f"| {r['id']} | {r['cat']} | {r['sev']} | {r['conf']} | {'**có**' if r['intervened'] else '-'} "
                     f"| {'✓' if r['ok_before'] else '✗'} → {'✓' if r['ok_after'] else '✗'} |")
        L.append("")
    tag = "" if len(sources) == 1 else "_" + "_".join(a.label)
    (out / f"heldout_guard{tag}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / f"heldout_guard{tag}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
