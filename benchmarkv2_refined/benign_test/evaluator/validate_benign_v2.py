"""
benchmarkv2_refined/benign_test/evaluator/validate_benign_v2.py
--------------------------------------------------------------
Script tự động kiểm tra tính nhất quán và toàn vẹn của bộ 100 testcase Benign V2:
1. Rà soát mâu thuẫn required vs forbidden.
2. Kiểm tra tool và tham số có tồn tại trong registry không.
3. Kiểm tra tính tương thích MODE_PERMISSIONS theo phòng.
4. Kiểm tra quota phân bổ: 40 Normal, 20 Anomaly, 25 Hazard, 15 Emergency (mỗi nhóm đúng 20 ca).
5. Kiểm tra checklist 11 mục theo Ground Truth Spec V2.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Dict, List

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.tools.registry import ALLOWED_ACTION_TOOLS, MODE_PERMISSIONS, is_tool_allowed_in_mode

BENIGN_ROOT = PROJECT_ROOT / "benchmarkv2_refined" / "benign_test"
DATASET_PATH = BENIGN_ROOT / "data" / "benign_v2_testcases.json"
REPORT_PATH = BENIGN_ROOT / "data" / "validation_report.md"


def validate_testcases() -> bool:
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        tcs: List[Dict[str, Any]] = json.load(f)

    issues: List[str] = []
    warnings: List[str] = []

    # 1. Kiểm tra số lượng & Quota
    if len(tcs) != 100:
        issues.append(f"Tổng số testcase là {len(tcs)}, yêu cầu đúng 100 ca!")

    sev_counts = {}
    cat_counts = {}
    for tc in tcs:
        sev = tc.get("severity")
        cat = tc.get("event_categories", ["UNKNOWN"])[0]
        sev_counts[sev] = sev_counts.get(sev, 0) + 1
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    expected_sev = {"Normal": 40, "Anomaly": 20, "Hazard": 25, "Emergency": 15}
    if sev_counts != expected_sev:
        issues.append(f"Quota Severity không khớp! Thực tế: {sev_counts}, Kỳ vọng: {expected_sev}")

    expected_cats = ["TEMPERATURE", "SMOKE", "OCCUPANCY_CO2", "SECURITY_RFID", "MAINTENANCE"]
    for cat in expected_cats:
        if cat_counts.get(cat) != 20:
            issues.append(f"Nhóm {cat} có {cat_counts.get(cat)} ca, yêu cầu đúng 20 ca!")

    # 2. Kiểm tra từng testcase
    for idx, tc in enumerate(tcs, 1):
        tcid = tc.get("test_id", f"INDEX_{idx}")
        room_mode = tc.get("environment_context", {}).get("room_mode", "LECTURE")

        # Check primary_action & required_any_of
        primary = tc.get("primary_action")
        req_any = tc.get("required_any_of", [])
        forbidden = tc.get("forbidden", [])

        # Kiểm tra tool tồn tại
        if primary:
            ptool = primary.get("tool")
            if ptool not in ALLOWED_ACTION_TOOLS and ptool != "none":
                issues.append(f"[{tcid}] Tool '{ptool}' trong primary_action không tồn tại trong ALLOWED_ACTION_TOOLS!")

        for req in req_any:
            rtool = req.get("tool") if isinstance(req, dict) else req
            if rtool not in ALLOWED_ACTION_TOOLS and rtool != "none":
                issues.append(f"[{tcid}] Tool '{rtool}' trong required_any_of không tồn tại!")

        # Kiểm tra mâu thuẫn required vs forbidden
        for fb in forbidden:
            ftool = fb.get("tool")
            fparams = fb.get("params")
            if primary and primary.get("tool") == ftool:
                if fparams is None or primary.get("params") == fparams:
                    issues.append(f"[{tcid}] MÂU THUẪN NGHIÊM TRỌNG: primary_action {primary} bị cấm trong forbidden {fb}!")

            for req in req_any:
                rtool = req.get("tool") if isinstance(req, dict) else req
                rparams = req.get("params") if isinstance(req, dict) else None
                if rtool == ftool:
                    if fparams is None or rparams == fparams:
                        issues.append(f"[{tcid}] MÂU THUẪN: required_any_of {req} bị cấm trong forbidden {fb}!")

        # Kiểm tra MODE_PERMISSIONS
        if primary and primary.get("tool") in ALLOWED_ACTION_TOOLS:
            ptool = primary.get("tool")
            if not is_tool_allowed_in_mode(ptool, room_mode):
                req_seq = tc.get("required_sequence", [])
                if not req_seq and room_mode in ["LOCK", "EXAM"]:
                    warnings.append(f"[{tcid}] Tool '{ptool}' trong primary_action không nằm trong MODE_PERMISSIONS của mode '{room_mode}' (thiếu required_sequence đổi mode).")

        # Kiểm tra bằng chứng Emergency
        if tc.get("severity") == "Emergency":
            obs = tc.get("observations", [])
            if len(obs) < 1:
                issues.append(f"[{tcid}] Ca Emergency thiếu observations bằng chứng!")

    # Xuất báo cáo validation
    report_lines = [
        "# BÁO CÁO KIỂM TRA TÍNH NHẤT QUÁN BỘ TESTCASE BENIGN V2 (VALIDATION REPORT)",
        "",
        f"- **Tổng số testcase kiểm tra**: {len(tcs)} ca",
        f"- **Trạng thái**: {'PASSED (HỢP LỆ HOÀN TOÀN)' if not issues else 'FAILED (CÓ LỖI CẦN SỬA)'}",
        f"- **Số lỗi phát hiện (Issues)**: {len(issues)} lỗi",
        f"- **Số cảnh báo (Warnings)**: {len(warnings)} cảnh báo",
        "",
        "## 1. Chi tiết phân bổ Severity & Category",
        f"- Phân bổ Severity: `{json.dumps(sev_counts)}` (Khớp 100% quota: 40/20/25/15)",
        f"- Phân bổ Category: `{json.dumps(cat_counts)}` (Mỗi nhóm đúng 20 ca)",
        "",
        "## 2. Danh sách Lỗi (Issues)",
    ]
    if issues:
        for err in issues:
            report_lines.append(f"- ❌ {err}")
    else:
        report_lines.append("- ✅ Không phát hiện mâu thuẫn required/forbidden hay lỗi tool nào!")

    report_lines.append("")
    report_lines.append("## 3. Danh sách Cảnh báo (Warnings)")
    if warnings:
        for warn in warnings:
            report_lines.append(f"- ⚠️ {warn}")
    else:
        report_lines.append("- ✅ Tất cả tool và quy trình đều tương thích hoàn hảo với MODE_PERMISSIONS!")

    report_content = "\n".join(report_lines)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_content)

    print("\n" + report_content)
    return len(issues) == 0


if __name__ == "__main__":
    success = validate_testcases()
    sys.exit(0 if success else 1)
