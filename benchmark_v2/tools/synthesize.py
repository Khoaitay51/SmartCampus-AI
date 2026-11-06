#!/usr/bin/env python3
"""
benchmark_v2/tools/synthesize.py
--------------------------------
Bộ công cụ xác định (deterministic) tổng hợp dataset Track A cho Benchmark v2:
- Tích Descartes: 5 User Cases (U1..U5) x 60 Attackers = 300 attack testcases.
- Bộ đối chứng sạch: 5 User Cases x 3 neutral descriptions = 15 benign testcases (BU).
- Áp dụng các quy tắc tự động pair_valid (§8, C6).
- Sinh event_id xác định bằng UUIDv5.
- Xuất dữ liệu ra data/generated/trackA_testcases.json và báo cáo synthesis_report.md.
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Tuple
import uuid

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

UUID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # DNS namespace
T0 = "2026-11-02T09:15:00+07:00"


def _tool_action_matches(pattern: Any, goal: Dict[str, Any]) -> bool:
    """Kiểm tra xem pattern trong expected_benign có trùng với goal của attacker không."""
    if not isinstance(goal, dict):
        return False
    goal_tool = goal.get("tool")
    if not goal_tool:
        return False

    if isinstance(pattern, str):
        return pattern == goal_tool

    if isinstance(pattern, dict):
        p_tool = pattern.get("tool")
        if p_tool != goal_tool:
            return False
        p_params = pattern.get("params")
        if p_params is None:
            # Pattern không chỉ định params cụ thể -> bất kỳ params nào cũng khớp
            return True
        g_params = goal.get("params", {})
        for k, v in p_params.items():
            if g_params.get(k) != v:
                return False
        return True

    return False


def check_pair(u: Dict[str, Any], a: Dict[str, Any]) -> Tuple[bool, str | None]:
    """
    Quy tắc kiểm tra tính hợp lệ của cặp User Case x Attacker:
    1. SUP: nếu u.requires_protective_action = False (U5) -> pair_valid = False
    2. DH-A / DH-S: nếu goal của attacker giao với expected_benign.required_any_of hoặc allowed -> pair_valid = False
    3. DS: kiểm tra tool S1/S2 có trong danh mục hay không
    """
    cat = a.get("category")
    uid = u.get("user_id")

    # Quy tắc 1: SUP trên phòng không cần bảo vệ (U5)
    if cat == "SUP":
        if not u.get("requires_protective_action", True):
            return False, f"SUP không áp dụng cho {uid} (phòng vận hành bình thường, không có nghĩa vụ bảo vệ)"

    # Quy tắc 2: DH giao với hành vi benign (bắt buộc hoặc cho phép)
    if cat in ["DH-A", "DH-S"]:
        goal = a.get("goal", {})
        exp = u.get("expected_benign", {})
        req_list = exp.get("required_any_of", [])
        allow_list = exp.get("allowed", [])

        # Kiểm tra giao với required_any_of
        for act in req_list:
            if _tool_action_matches(act, goal):
                return False, f"Mục tiêu tấn công {goal.get('tool')} trùng với hành động bảo vệ bắt buộc của {uid}"

        # Kiểm tra giao với allowed
        for act in allow_list:
            if _tool_action_matches(act, goal):
                return False, f"Mục tiêu tấn công {goal.get('tool')} trùng với hành động được phép của {uid}"

    # Quy tắc 3: DS tools hợp lệ
    if cat == "DS":
        goal = a.get("goal", {})
        s1 = goal.get("s1", {}).get("tool")
        valid_s1 = ["read_room_notes", "read_access_log", "get_telemetry", "get_room_history"]
        if s1 not in valid_s1:
            return False, f"Tool S1 '{s1}' không có trong registry"

    return True, None


def fill_placeholders(text: str, room_label: str) -> str:
    """Thay thế placeholder {ROOM} hoặc {{ROOM}} bằng nhãn phòng."""
    res = text.replace("{ROOM}", room_label).replace("{{ROOM}}", room_label)
    if re.search(r"\{[A-Za-z0-9_]+\}", res):
        raise ValueError(f"Còn sót placeholder chưa thay thế trong text: {res}")
    return res


def synthesize(data_dir: Path, out_dir: Path) -> Tuple[List[Dict[str, Any]], str]:
    """Hàm tổng hợp chính."""
    u_file = data_dir / "user_cases.json"
    a_file = data_dir / "attackers.json"

    with open(u_file, encoding="utf-8") as f:
        user_cases: List[Dict[str, Any]] = json.load(f)

    with open(a_file, encoding="utf-8") as f:
        attackers: List[Dict[str, Any]] = json.load(f)

    out_dir.mkdir(parents=True, exist_ok=True)
    testcases: List[Dict[str, Any]] = []

    # 1. Sinh các cặp Attack (5 x 60 = 300)
    for u in user_cases:
        uid = u["user_id"]
        r_label = u["room_label"]
        r_id = u["room_id"]

        for a in attackers:
            aid = a["attacker_id"]
            tc_id = f"V2A_{uid}_{aid}"
            valid, reason = check_pair(u, a)

            # Render payload text
            injected_desc = fill_placeholders(a["payload_text"], r_label)

            # Render packet
            packet = deepcopy(u["packet_template"])
            packet["room_id"] = r_id
            packet["timestamp"] = T0
            packet["event_data"]["description"] = injected_desc

            # Sinh deterministic UUIDv5
            ev_id = str(uuid.uuid5(UUID_NAMESPACE, tc_id))
            packet["event_id"] = ev_id

            tc = {
                "testcase_id": tc_id,
                "track": "A",
                "kind": "attack",
                "user_id": uid,
                "attacker_id": aid,
                "category": a["category"],
                "persuasion": a["persuasion"],
                "room_label": r_label,
                "room_id": r_id,
                "trigger_instruction": u["trigger_instruction"],
                "payload": {
                    "event": packet,
                    "operational_context": deepcopy(u.get("operational_context", {}))
                },
                "goal": deepcopy(a["goal"]),
                "expected_benign": deepcopy(u["expected_benign"]),
                "requires_protective_action": u.get("requires_protective_action", True),
                "env_ref": u.get("env_ref", f"env_spec.rooms[{uid}]"),
                "reference_time": T0,
                "pair_valid": valid,
                "invalid_reason": reason
            }
            testcases.append(tc)

    # 2. Sinh các ca Benign Controls (BU: 5 x 3 = 15)
    for u in user_cases:
        uid = u["user_id"]
        r_label = u["room_label"]
        r_id = u["room_id"]

        neutrals = u.get("neutral_descriptions", [])
        for k, desc in enumerate(neutrals, 1):
            tc_id = f"V2A_{uid}_BU{k}"
            packet = deepcopy(u["packet_template"])
            packet["room_id"] = r_id
            packet["timestamp"] = T0
            packet["event_data"]["description"] = fill_placeholders(desc, r_label)
            ev_id = str(uuid.uuid5(UUID_NAMESPACE, tc_id))
            packet["event_id"] = ev_id

            tc = {
                "testcase_id": tc_id,
                "track": "A",
                "kind": "benign",
                "user_id": uid,
                "attacker_id": None,
                "category": "BENIGN",
                "persuasion": "none",
                "room_label": r_label,
                "room_id": r_id,
                "trigger_instruction": u["trigger_instruction"],
                "payload": {
                    "event": packet,
                    "operational_context": deepcopy(u.get("operational_context", {}))
                },
                "goal": None,
                "expected_benign": deepcopy(u["expected_benign"]),
                "requires_protective_action": u.get("requires_protective_action", True),
                "env_ref": u.get("env_ref", f"env_spec.rooms[{uid}]"),
                "reference_time": T0,
                "pair_valid": True,
                "invalid_reason": None
            }
            testcases.append(tc)

    # Ghi file JSON xác định
    json_path = out_dir / "trackA_testcases.json"
    content_bytes = json.dumps(testcases, ensure_ascii=False, indent=2).encode("utf-8")
    with open(json_path, "wb") as f:
        f.write(content_bytes)

    file_hash = hashlib.sha256(content_bytes).hexdigest()

    # Sinh báo cáo Markdown
    report_path = out_dir / "synthesis_report.md"
    report_md = _generate_report(testcases, user_cases, attackers, file_hash)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    return testcases, file_hash


def _generate_report(
    testcases: List[Dict[str, Any]],
    user_cases: List[Dict[str, Any]],
    attackers: List[Dict[str, Any]],
    sha256_hash: str
) -> str:
    total = len(testcases)
    attacks = [tc for tc in testcases if tc["kind"] == "attack"]
    benigns = [tc for tc in testcases if tc["kind"] == "benign"]

    valid_attacks = [tc for tc in attacks if tc["pair_valid"]]
    invalid_attacks = [tc for tc in attacks if not tc["pair_valid"]]

    u_ids = [u["user_id"] for u in user_cases]
    cats = ["DH-A", "DH-S", "SUP", "DS"]

    lines = [
        "# BÁO CÁO TỔNG HỢP DATASET TRACK A (SYNTHESIS REPORT)",
        "",
        f"- **Thời gian tham chiếu (T0):** `{T0}`",
        f"- **Tổng số testcase:** `{total}` (Gồm {len(attacks)} ca Attack + {len(benigns)} ca Benign Đối chứng)",
        f"- **Số ca Attack hợp lệ (`pair_valid = True`):** `{len(valid_attacks)}`",
        f"- **Số ca Attack bị lọc (`pair_valid = False`):** `{len(invalid_attacks)}`",
        f"- **SHA-256 Checksum (`trackA_testcases.json`):** `{sha256_hash}`",
        "",
        "---",
        "",
        "## 1. Ma trận Tích Descartes (User Cases x Category)",
        "",
        "| User Case | DH-A (hợp lệ / tổng) | DH-S (hợp lệ / tổng) | SUP (hợp lệ / tổng) | DS (hợp lệ / tổng) | BU (Benign) | Tổng hợp lệ |",
        "|---|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]

    for uid in u_ids:
        row = [f"**{uid}**"]
        u_valid_count = 0
        for cat in cats:
            sub = [tc for tc in attacks if tc["user_id"] == uid and tc["category"] == cat]
            sub_valid = [tc for tc in sub if tc["pair_valid"]]
            row.append(f"{len(sub_valid)}/{len(sub)}")
            u_valid_count += len(sub_valid)
        u_benigns = [tc for tc in benigns if tc["user_id"] == uid]
        row.append(str(len(u_benigns)))
        u_valid_count += len(u_benigns)
        row.append(f"**{u_valid_count}**")
        lines.append("| " + " | ".join(row) + " |")

    lines.extend([
        "",
        "---",
        "",
        "## 2. Chi tiết các Ca Bị Lọc (`pair_valid = False`)",
        "",
        f"Tổng cộng có **{len(invalid_attacks)}** ca bị đánh dấu `pair_valid = false`:",
        "",
        "| # | Testcase ID | Nhóm | Attacker ID | Lý do lọc tự động |",
        "|---|---|:---:|---|---|",
    ])

    for idx, tc in enumerate(invalid_attacks, 1):
        lines.append(f"| {idx} | `{tc['testcase_id']}` | `{tc['category']}` | `{tc['attacker_id']}` | {tc['invalid_reason']} |")

    lines.extend([
        "",
        "---",
        "",
        "## 3. Kết luận và Ràng buộc Benchmark v2",
        "1. **Tính xác định (Determinism):** Mọi ID, Event ID (UUIDv5), và thứ tự bản ghi được cố định 100%.",
        "2. **Phạm vi tính Metric:**",
        "   - `ASR-valid` chỉ tính trên các ca có `pair_valid = True`.",
        "   - `ASR-all` tính trên toàn bộ 300 ca (để đối chiếu robustness).",
        "   - `BU` (Benign Utility) tính trên 15 ca `V2A_Ux_BUk`.",
        "   - `UA` (Utility under Attack) tính trên các ca attack.",
    ])

    return "\n".join(lines)


def main():
    base_dir = Path("AI + Backend/benchmark_v2") if Path("AI + Backend/benchmark_v2").exists() else Path("benchmark_v2")
    data_dir = base_dir / "data"
    out_dir = data_dir / "generated"

    testcases, h = synthesize(data_dir, out_dir)
    print("=" * 60)
    print("TỔNG HỢP DATASET TRACK A HOÀN TẤT")
    print("=" * 60)
    print(f"Tổng số testcases: {len(testcases)}")
    valid_count = sum(1 for tc in testcases if tc.get("pair_valid"))
    print(f"Số ca hợp lệ (pair_valid=True): {valid_count}/{len(testcases)}")
    print(f"File đầu ra: {out_dir / 'trackA_testcases.json'}")
    print(f"Báo cáo: {out_dir / 'synthesis_report.md'}")
    print(f"SHA-256: {h}")
    print("=" * 60)


if __name__ == "__main__":
    main()
