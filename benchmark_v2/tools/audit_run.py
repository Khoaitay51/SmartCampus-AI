"""Audit tính toàn vẹn của một lượt chạy (phục vụ rà soát release). Chỉ đọc, không sửa dữ liệu."""
import json
import sys
import io
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
run_id = sys.argv[1]
base = Path(__file__).resolve().parents[1] / "results" / run_id
rows = [json.loads(l) for l in open(base / "raw_runs.jsonl", encoding="utf-8") if l.strip()]

print("== N:", len(rows), " unique(tc,rep):", len({(r["testcase_id"], r["repeat_idx"]) for r in rows}))
print("== run_status:", Counter(r["run_status"] for r in rows))
print("== is_fallback:", Counter(r["is_fallback"] for r in rows))
print("== fallback_reason:", Counter((r["fallback_reason"] or "")[:60] for r in rows if r["is_fallback"] or r["run_status"] != "OK"))
fb_levels = Counter()
for r in rows:
    a = r.get("analysis") or ""
    if a.startswith("[FALLBACK"):
        fb_levels[a.split("]")[0]] += 1
print("== analysis FALLBACK tags:", fb_levels)

print("== fallback theo category:")
bycat = defaultdict(lambda: [0, 0])
for r in rows:
    k = r.get("category") or r["kind"]
    bycat[k][1] += 1
    if r["is_fallback"]:
        bycat[k][0] += 1
for k, v in bycat.items():
    print("  ", k, v)

lat = sorted(r["latency_ms"] for r in rows)
print("== latency ms: median", lat[len(lat) // 2], " p95", lat[int(len(lat) * 0.95)], " max", lat[-1])
print("== TIMEOUT cases:", [(r["testcase_id"], r["latency_ms"]) for r in rows if r["run_status"] == "TIMEOUT"])
print("== latency > 60000:", [(r["testcase_id"], r["latency_ms"]) for r in rows if r["latency_ms"] > 60000])

print("== tokens theo track/category:")
tk = defaultdict(lambda: [0, 0, 0])
for r in rows:
    k = r.get("category") or r["kind"]
    tk[k][0] += r["tokens"]["in"]
    tk[k][1] += r["tokens"]["out"]
    tk[k][2] += 1
for k, v in tk.items():
    print("  ", k, "in", v[0], "out", v[1], "n", v[2], "avg_in", v[0] // max(1, v[2]))
print("== ca tokens==0:", sum(1 for r in rows if r["tokens"]["in"] == 0))
print("== skip/none count:", Counter(r["skip"] for r in rows))
