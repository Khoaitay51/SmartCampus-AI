"""Sinh manifest.json cho lượt chạy + kiểm tra hash đóng băng + test-retest Pilot vs E3. Chỉ đọc dữ liệu gốc."""
import hashlib
import io
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
BV2 = ROOT / "benchmark_v2"
sys.path.insert(0, str(ROOT))
from benchmark_v2.evaluator.evaluate_v2 import EvaluatorV2  # noqa: E402

run_id = sys.argv[1]
pilot_id = sys.argv[2]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


frozen = {
    "data/env_spec.json": "373ebc804d7dcef1027c67d1b69d85fcd18322c09a1b3f4a2a1654de80c45abd",
    "data/triage_v1.csv": "d2275b00e23ff6fe68c509462d4a3e27fcb4108566fff1f50b1624539778bbe0",
    "data/attackers.json": "89776b0e8edc070ae2f11f1eb9f0873046a17dd27b4ba6e66e5b4d13368a1d8f",
    "data/user_cases.json": "f36ac4bd420e03acac01bb6914622f4c09fb2406692d92e5af6a44c8a31d0bad",
    "data/generated/trackA_testcases.json": "48f94b8c77cd56816c080b9dfed18699e72a2265eeb6b53b46c11c9acaaa614d",
    "data/generated/synthesis_report.md": "db3f7458343dc8938edb4eb670c7bca49feec4d9a4b5cdb653b0c229e2e4d0c7",
    "data/trackB_testcases.json": "f6745b44b5e2c7f311e36800a10eda5ab75834634474bb16655a1b09a3770f97",
    "ANALYSIS_PLAN.md": "505cd8af0d9a21c4ba0a56af3329a1f6ab186633337049a0d27b06eb170cbb0c",
}
print("== Kiểm tra hash đóng băng dataset")
all_ok = True
for rel, h in frozen.items():
    cur = sha(BV2 / rel)
    ok = cur == h
    all_ok &= ok
    print(f"  {'OK ' if ok else 'LỆCH'} {rel}")
print("  => TẤT CẢ KHỚP" if all_ok else "  => CÓ FILE BỊ THAY ĐỔI SAU ĐÓNG BĂNG!")

# fingerprint mã nguồn (working tree chưa commit)
def run(cmd):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout

head = run(["git", "rev-parse", "HEAD"]).strip()
diff = run(["git", "diff", "HEAD", "--", "app"])
untracked = [l[3:].strip().strip('"') for l in run(["git", "status", "-s", "--", "app"]).splitlines() if l.startswith("??")]
diff_hash = hashlib.sha256(diff.encode("utf-8")).hexdigest()
ut_hash = {}
for u in untracked:
    p = ROOT / u
    if p.is_file():
        ut_hash[u] = sha(p)
print("\n== HEAD:", head, "| sha256(git diff HEAD -- app):", diff_hash, "| untracked app files:", ut_hash)

res = BV2 / "results" / run_id
files = {}
for n in ["raw_runs.jsonl", "summary.json", "report.md"]:
    files[n] = sha(res / n)
code = {
    "evaluator/evaluate_v2.py": sha(BV2 / "evaluator/evaluate_v2.py"),
    "runner/run_benchmark.py": sha(BV2 / "runner/run_benchmark.py"),
    "env/env_manifest.json": sha(BV2 / "env/env_manifest.json"),
}
manifest = {
    "run_id": run_id,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "git_head": head,
    "git_working_tree_dirty": bool(diff.strip() or untracked),
    "app_diff_sha256": diff_hash,
    "app_untracked_sha256": ut_hash,
    "frozen_dataset_hashes_verified": all_ok,
    "result_files_sha256": files,
    "tool_files_sha256": code,
    "command": f"python benchmark_v2/runner/run_benchmark.py --track all --run-id {run_id}",
    "model": "gemini-3.5-flash-lite", "k": 1, "temperature": 0.0, "timeout_s": 60, "disable_fallback": True,
}
(res / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print("\n== Đã ghi", res / "manifest.json")

# ---- test-retest: Pilot (65 ca) vs E3 trên cùng testcase_id, cùng cấu hình
ev = EvaluatorV2(BV2 / "data")
def load(rid):
    out = {}
    for l in open(BV2 / "results" / rid / "raw_runs.jsonl", encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            out[r["testcase_id"]] = (r, ev.evaluate_track_a_run(r))
    return out

P, E = load(pilot_id), load(run_id)
common = sorted(set(P) & set(E))
def final_tool(r):
    rec = [s for s in r["trajectory"] if s["source"] == "recommendation"]
    return (rec[-1]["tool"] if rec else None)
same_tool = sum(final_tool(P[c][0]) == final_tool(E[c][0]) for c in common)
atk = [c for c in common if E[c][1]["kind"] == "attack" and E[c][1]["pair_valid"]]
both = sum(P[c][1]["attack_success"] == E[c][1]["attack_success"] for c in atk)
n11 = sum(P[c][1]["attack_success"] and E[c][1]["attack_success"] for c in atk)
n10 = sum(P[c][1]["attack_success"] and not E[c][1]["attack_success"] for c in atk)
n01 = sum((not P[c][1]["attack_success"]) and E[c][1]["attack_success"] for c in atk)
n00 = len(atk) - n11 - n10 - n01
po = (n11 + n00) / len(atk)
pp, pe_ = (n11 + n10) / len(atk), (n11 + n01) / len(atk)
pe = pp * pe_ + (1 - pp) * (1 - pe_)
kappa = (po - pe) / (1 - pe) if pe < 1 else float("nan")
print(f"\n== TEST-RETEST (Pilot vs E3), {len(common)} ca chung; {len(atk)} ca attack hợp lệ")
print(f"  Cùng tool cuối cùng: {same_tool}/{len(common)} = {same_tool/len(common)*100:.1f}%")
print(f"  attack_success giống nhau: {both}/{len(atk)} = {both/len(atk)*100:.1f}% | bảng (P,E): 11={n11} 10={n10} 01={n01} 00={n00} | Cohen kappa={kappa:.3f}")
print(f"  ASR trong pilot-subset: pilot {(n11+n10)}/{len(atk)} vs E3 {(n11+n01)}/{len(atk)}")
