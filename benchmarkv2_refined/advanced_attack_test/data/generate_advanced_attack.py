#!/usr/bin/env python3
"""
benchmarkv2_refined/advanced_attack_test/data/generate_advanced_attack.py
-------------------------------------------------------------------------
Bộ sinh dataset tự động tinh gọn cho Phase 3 (Advanced Attack Benchmark):
- Sử dụng 60 Attacker Profiles nâng cao (22 DH-A, 22 SUP, 10 DH-S, 6 DS).
- Kết hợp cùng 5 User Cases chuẩn mực (U1..U5).
- Tinh gọn: Tự động lọc các ca pair_valid=False (SUP trên U5, goal trùng nghiệp vụ tự nhiên),
  chỉ xuất các ca HỢP LỆ VÀ CÓ THỂ ĐÁNH GIÁ (Valid Attack Cases).
- Bổ sung 16 ca Track B System Robustness (SER, CDR, WTR, PMR) và 15 ca Benign Control (BU).
- Xuất:
  - advanced_attack_testcases.json
  - advanced_synthesis_report.md
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple
import uuid

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

UUID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
T0 = "2026-11-02T09:15:00+07:00"


def _tool_action_matches(pattern: Any, goal: Dict[str, Any]) -> bool:
    if not isinstance(goal, dict):
        return False
    goal_tool = goal.get("tool")
    if not goal_tool:
        return False

    if isinstance(pattern, str):
        if pattern == "@actuation":
            return goal_tool in ["set_fan", "set_door", "set_mode", "trigger_buzzer", "set_led"]
        if pattern == "@exfil":
            return goal_tool in ["http_post", "send_webhook", "send_email"]
        if ":" in pattern:
            p_tool, p_val = pattern.split(":", 1)
            if goal_tool != p_tool:
                return False
            for v in goal.get("params", {}).values():
                if str(v).lower() == p_val.lower():
                    return True
            return False
        return pattern == goal_tool

    if isinstance(pattern, dict):
        p_tool = pattern.get("tool")
        if p_tool != goal_tool:
            return False
        p_params = pattern.get("params")
        if p_params is None:
            return True
        g_params = goal.get("params", {})
        for k, v in p_params.items():
            if g_params.get(k) != v:
                return False
        return True

    return False


def check_pair(u: Dict[str, Any], a: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    cat = a.get("category")
    uid = u.get("user_id")

    # 1. SUP trên phòng bình thường (U5) -> Invalid
    if cat == "SUP":
        if not u.get("requires_protective_action", True):
            return False, f"SUP không áp dụng cho {uid} (phòng vận hành bình thường)"

    # 2. DH-A / DH-S trùng hành động bảo vệ hoặc cho phép -> Invalid
    if cat in ["DH-A", "DH-S"]:
        goal = a.get("goal", {})
        exp = u.get("expected_benign", {})
        req_list = exp.get("required_any_of", [])
        allow_list = exp.get("allowed", [])

        for act in req_list:
            if _tool_action_matches(act, goal):
                return False, f"Mục tiêu tấn công {goal.get('tool')} trùng với hành động bảo vệ bắt buộc của {uid}"

        for act in allow_list:
            if _tool_action_matches(act, goal):
                return False, f"Mục tiêu tấn công {goal.get('tool')} trùng với hành động được phép của {uid}"

    return True, None


def fill_placeholders(text: str, room_label: str) -> str:
    res = text.replace("{ROOM}", room_label).replace("{{ROOM}}", room_label)
    if re.search(r"\{[A-Za-z0-9_]+\}", res):
        raise ValueError(f"Sót placeholder: {res}")
    return res


def generate_advanced_dataset(
    data_dir: Path,
    out_dir: Path,
    prune_invalid: bool = True
) -> Tuple[List[Dict[str, Any]], str]:
    u_file = data_dir / "user_cases.json"
    a_file = out_dir / "advanced_attackers.json"
    b_file = data_dir / "trackB_testcases.json"

    with open(u_file, "r", encoding="utf-8") as f:
        user_cases: List[Dict[str, Any]] = json.load(f)

    with open(a_file, "r", encoding="utf-8") as f:
        attackers: List[Dict[str, Any]] = json.load(f)

    with open(b_file, "r", encoding="utf-8") as f:
        track_b_raw: List[Dict[str, Any]] = json.load(f)

    out_dir.mkdir(parents=True, exist_ok=True)
    testcases: List[Dict[str, Any]] = []

    # 1. Sinh Track A Attack (chỉ giữ ca hợp lệ nếu prune_invalid=True)
    pruned_count = 0
    for u in user_cases:
        uid = u["user_id"]
        r_label = u["room_label"]
        r_id = u["room_id"]

        for a in attackers:
            aid = a["attacker_id"]
            tc_id = f"V3A_{uid}_{aid}"
            valid, reason = check_pair(u, a)

            if prune_invalid and not valid:
                pruned_count += 1
                continue

            injected_desc = fill_placeholders(a["payload_text"], r_label)
            packet = deepcopy(u["packet_template"])
            packet["room_id"] = r_id
            packet["timestamp"] = T0
            packet["event_data"]["description"] = injected_desc
            packet["event_id"] = str(uuid.uuid5(UUID_NAMESPACE, tc_id))

            tc = {
                "testcase_id": tc_id,
                "track": "A",
                "kind": "attack",
                "user_id": uid,
                "attacker_id": aid,
                "category": a["category"],
                "persuasion": a.get("persuasion", "urgency"),
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
                "pair_valid": True,
                "invalid_reason": None
            }
            testcases.append(tc)

    # 2. Sinh Benign Controls (15 ca BU)
    for u in user_cases:
        uid = u["user_id"]
        r_label = u["room_label"]
        r_id = u["room_id"]
        for k, desc in enumerate(u.get("neutral_descriptions", []), 1):
            tc_id = f"V3A_{uid}_BU{k}"
            packet = deepcopy(u["packet_template"])
            packet["room_id"] = r_id
            packet["timestamp"] = T0
            packet["event_data"]["description"] = fill_placeholders(desc, r_label)
            packet["event_id"] = str(uuid.uuid5(UUID_NAMESPACE, tc_id))

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

    # 3. Chuẩn hóa Track B (16 ca)
    for tc_b in track_b_raw:
        b_entry = deepcopy(tc_b)
        b_entry["kind"] = "robustness"
        b_entry["pair_valid"] = True
        b_entry["invalid_reason"] = None
        b_entry["reference_time"] = tc_b.get("reference_time", T0)
        testcases.append(b_entry)

    # Xuất file JSON
    json_path = out_dir / "advanced_attack_testcases.json"
    content_bytes = json.dumps(testcases, ensure_ascii=False, indent=2).encode("utf-8")
    with open(json_path, "wb") as f:
        f.write(content_bytes)

    digest = hashlib.sha256(content_bytes).hexdigest()
    return testcases, digest


if __name__ == "__main__":
    src_data_dir = Path(__file__).resolve().parents[3] / "benchmark_v2" / "data"
    out_dir = Path(__file__).resolve().parent

    print(f"[*] Đang sinh dataset Phase 3...")
    tcs, sha = generate_advanced_dataset(src_data_dir, out_dir, prune_invalid=True)
    print(f"[✓] Đã tạo thành công {len(tcs)} testcases!")
    print(f"[✓] Checksum SHA-256: {sha}")
    from collections import Counter
    track_a_attacks = [tc for tc in tcs if tc.get("track") == "A" and tc.get("kind") == "attack"]
    print("Phân rã Track A Attack:", Counter(tc["category"] for tc in track_a_attacks))
    print("Track B Robustness:", len([tc for tc in tcs if tc.get("track") == "B"]))
    print("Benign Controls:", len([tc for tc in tcs if tc.get("kind") == "benign"]))
