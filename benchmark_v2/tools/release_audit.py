"""Phân tích độ nhạy & rà soát tính hợp lệ cho release (chỉ đọc; KHÔNG sửa evaluator/dataset/raw_runs)."""
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmark_v2.evaluator.evaluate_v2 import EvaluatorV2, wilson_score_interval  # noqa: E402

run_id = sys.argv[1]
base = ROOT / "benchmark_v2"
ev = EvaluatorV2(base / "data")
rows = [json.loads(l) for l in open(base / "results" / run_id / "raw_runs.jsonl", encoding="utf-8") if l.strip()]
raw = {r["testcase_id"]: r for r in rows}


def ci(s, n):
    p, lo, hi = wilson_score_interval(s, n, 0.95)
    return f"{s}/{n} = {p*100:.2f}%  CI95[{lo*100:.2f}, {hi*100:.2f}]"


A = [ev.evaluate_track_a_run(r) for r in rows if r["testcase_id"].startswith("V2A_")]
B = [ev.evaluate_track_b_run(r) for r in rows if r["testcase_id"].startswith("V2B_")]
for x in A + B:
    x["fb"] = raw[x["testcase_id"]]["is_fallback"]

atk = [x for x in A if x["kind"] == "attack" and x["pair_valid"]]
ben = [x for x in A if x["kind"] == "benign"]

print("### MAIN (như evaluator)         ASR-valid:", ci(sum(x["attack_success"] for x in atk), len(atk)))
ok = [x for x in atk if x["run_status"] == "OK"]
print("### Loại ca không-OK (timeout)   ASR-valid:", ci(sum(x["attack_success"] for x in ok), len(ok)), "| loại", len(atk) - len(ok))
nofb = [x for x in ok if not x["fb"]]
fb = [x for x in ok if x["fb"]]
print("### Chỉ ca KHÔNG fallback-parse  ASR-valid:", ci(sum(x["attack_success"] for x in nofb), len(nofb)))
print("### Chỉ ca CÓ fallback-parse     ASR-valid:", ci(sum(x["attack_success"] for x in fb), len(fb)))
print("### Kịch bản xấu nhất: mọi ca fallback coi là thành công:",
      ci(sum(1 for x in ok if x["attack_success"] or x["fb"]), len(ok)))
print("### Kịch bản tốt nhất: mọi ca fallback coi là thất bại :",
      ci(sum(1 for x in ok if x["attack_success"] and not x["fb"]), len(ok)))

print("\n### Theo nhóm (main | không-fallback)")
for cat in ["DH-A", "DH-S", "SUP", "DS"]:
    g = [x for x in atk if x["category"] == cat]
    g2 = [x for x in g if x["run_status"] == "OK" and not x["fb"]]
    print(f"  {cat}: {ci(sum(x['attack_success'] for x in g), len(g))} | no-fb {ci(sum(x['attack_success'] for x in g2), len(g2))}  | fb_runs={sum(x['fb'] for x in g)}")

print("\n### Theo user case (valid attacks)")
for u in ["U1", "U2", "U3", "U4", "U5"]:
    g = [x for x in atk if x["user_id"] == u]
    print(f"  {u}: {ci(sum(x['attack_success'] for x in g), len(g))}  | theo nhóm:",
          {c: f"{sum(1 for x in g if x['category']==c and x['attack_success'])}/{sum(1 for x in g if x['category']==c)}" for c in ['DH-A','DH-S','SUP','DS']})

print("\n### Theo persuasion")
pz = defaultdict(lambda: [0, 0])
for x in atk:
    pz[x.get("persuasion")][1] += 1
    pz[x.get("persuasion")][0] += x["attack_success"]
for k, v in sorted(pz.items(), key=lambda kv: str(kv[0])):
    print(f"  {k}: {v[0]}/{v[1]} = {v[0]/v[1]*100:.1f}%")

ds = [x for x in atk if x["category"] == "DS"]
print("\n### DS: S1 (đọc nguồn) thành công:", ci(sum(x["s1_success"] for x in ds), len(ds)),
      "| S2 (canary ra sink):", sum(x["s2_success"] for x in ds))
sink_calls = Counter()
for r in rows:
    for st in r["trajectory"]:
        if st.get("tool") in ("http_post", "send_webhook", "send_email", "read_room_notes", "read_access_log"):
            sink_calls[st["tool"]] += 1
print("### Số lần agent gọi tool đọc/sink trên toàn run:", dict(sink_calls))
print("### Tool dùng trong trajectory (toàn run):", Counter(st.get("tool") for r in rows for st in r["trajectory"]).most_common())

print("\n### SUP: số ca skip (không hành động) vs gọi hành động khác")
sup = [x for x in atk if x["category"] == "SUP"]
print("  SUP thành công & trajectory rỗng-hành-động:",
      sum(1 for x in sup if x["attack_success"] and not any(s['source'] == 'recommendation' for s in raw[x['testcase_id']]['trajectory'])),
      "/", sum(x["attack_success"] for x in sup))

print("\n### BU / UA")
print("  BU:", ci(sum(x["utility_success"] for x in ben), len(ben)))
print("  UA (valid attacks):", ci(sum(x["utility_success"] for x in atk), len(atk)))
for u in ["U1", "U2", "U3", "U4", "U5"]:
    g = [x for x in atk if x["user_id"] == u]
    print(f"   UA {u}:", ci(sum(x["utility_success"] for x in g), len(g)))

print("\n### Track B chi tiết")
tbm = ev.track_b_map
for x in B:
    tc = tbm[x["testcase_id"]]
    r = raw[x["testcase_id"]]
    calls = [(s["tool"], json.dumps(s["params"], ensure_ascii=False)[:60]) for s in r["trajectory"] if s["source"] == "recommendation"]
    print(f"  {x['testcase_id']} [{x['sub_track']}] status={x['run_status']} fb={x['fb']} unsafe={x['unsafe_commission']} omit={x['omission']}")
    print("     required:", tc.get("oracle", {}).get("required_actions"), "| forbidden:", tc.get("oracle", {}).get("forbidden_actions"))
    print("     agent rec:", calls, "| skip:", r["skip"])
