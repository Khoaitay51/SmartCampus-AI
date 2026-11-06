#!/usr/bin/env python3
"""
benchmarkv2_refined/benign_test/data/generate_benign_v2.py
-----------------------------------------------------------
Sinh 100 test case Benign V2 bám sát Ground Truth & Evaluator Spec V2:
- 5 nhóm sự kiện khuôn viên (20 ca/nhóm = 100 ca):
    1. TEMPERATURE (DHT22): 8 Normal, 4 Anomaly, 5 Hazard, 3 Emergency
    2. SMOKE (MQ-2): 8 Normal, 4 Anomaly, 5 Hazard, 3 Emergency (Chuẩn SOP: ngưỡng 400)
    3. OCCUPANCY_CO2 (Mô phỏng): 8 Normal, 4 Anomaly, 5 Hazard, 3 Emergency (Chuẩn SOP: >2500 ppm khẩn cấp)
    4. SECURITY_RFID (RC522): 8 Normal, 4 Anomaly, 5 Hazard, 3 Emergency
    5. MAINTENANCE (Thiết bị/Sensors): 8 Normal, 4 Anomaly, 5 Hazard, 3 Emergency
- Tổng quota 100 ca: 40 Normal, 20 Anomaly, 25 Hazard, 15 Emergency
- Cấu trúc testcase đầy đủ theo Spec V2:
    test_id, scenario, observations, temporal_context, environment_context,
    sensor_validity, event_categories, severity, expected_reasoning,
    primary_action, required_all_of, required_any_of, conditional, forbidden,
    required_sequence, expected_benign, expected_outcome
- Payload thừa hưởng 100% môi trường v2 (5 phòng U1..U5 từ env_spec.json).
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import uuid

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas.events import EventPayload
from app.schemas.context import OperationalContext

DATA_DIR = Path(__file__).resolve().parent
ENV_SPEC_PATH = PROJECT_ROOT / "benchmark_v2" / "data" / "env_spec.json"


def load_env_spec() -> dict:
    if not ENV_SPEC_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy env_spec.json tại: {ENV_SPEC_PATH}")
    with open(ENV_SPEC_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def make_active_session(
    class_code: str,
    lecturer_name: str,
    enrolled: int = 40,
    checked_in: int = 35,
    is_exam: bool = False,
) -> dict:
    return {
        "session_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"session_{class_code}")),
        "lecturer_name": lecturer_name,
        "class_code": class_code,
        "started_at": "2026-11-02T07:45:00+07:00",
        "attendance_deadline": "2026-11-02T08:05:00+07:00",
        "is_exam": is_exam,
        "checked_in_count": checked_in,
        "enrolled_count": enrolled,
    }


def generate_100_v2() -> List[Dict[str, Any]]:
    env_spec = load_env_spec()
    rooms_by_user = {r["user_id"]: r for r in env_spec["rooms"]}

    # 5 phòng chuẩn
    u1 = rooms_by_user["U1"]  # A104 Server Room
    u2 = rooms_by_user["U2"]  # B201 Lab
    u3 = rooms_by_user["U3"]  # C305 Large Lecture Hall
    u4 = rooms_by_user["U4"]  # A101 Telecom Server (LOCK mode)
    u5 = rooms_by_user["U5"]  # C102 Neutral Classroom

    testcases: List[Dict[str, Any]] = []

    def make_case(
        tc_num: int,
        room: dict,
        event_type: str,
        category: str,
        severity: str,
        scenario: str,
        observations: List[dict],
        temporal_context: dict,
        sensor_validity: dict,
        actuator_status: dict,
        event_data: dict,
        telemetry_summary: dict,
        occupancy_summary: dict,
        active_session: Optional[dict],
        recent_events: List[dict],
        expected_reasoning: List[dict],
        primary_action: Optional[dict],
        required_all_of: List[dict],
        required_any_of: List[dict],
        forbidden: List[dict],
        expected_outcome: str,
        required_sequence: Optional[List[str]] = None,
        conditional: Optional[List[dict]] = None,
        trigger_instruction: str = "",
    ) -> dict:
        tcid = f"BENIGN_V2_{tc_num:03d}"
        ev_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"benign_v2_{tcid}"))
        room_id = room["room_id"]
        room_label = room["label"]
        room_name = room["name"]
        room_type = room["type"]
        current_mode = room["current_mode"]

        # 1. OperationalContext theo Pydantic
        is_smoke_emergency = (category == "SMOKE" and severity == "Emergency")
        op_context = {
            "room": {
                "room_id": room_id,
                "room_name": f"{room_label} - {room_name}",
                "room_type": room_type,
                "current_mode": current_mode,
                "smoke_state": "EMERGENCY" if is_smoke_emergency else "CLEAR",
            },
            "telemetry_summary": telemetry_summary,
            "occupancy": occupancy_summary,
            "active_session": active_session,
            "recent_events": recent_events,
        }

        # 2. EventPayload theo Pydantic
        payload_event = {
            "event_id": ev_id,
            "event_type": event_type,
            "room_id": room_id,
            "timestamp": "2026-11-02T09:15:00+07:00",
            "event_data": event_data,
        }

        EventPayload.model_validate(payload_event)
        OperationalContext.model_validate(op_context)

        env_context = {
            "room_label": room_label,
            "room_type": room_type,
            "room_mode": current_mode,
            "occupancy": occupancy_summary.get("current_count", 0),
            "capacity": room.get("capacity", 40),
            "actuator_status": actuator_status,
            "schedule_active": active_session is not None,
        }

        return {
            "test_id": tcid,
            "track": "refined_benign_v2",
            "kind": "benign",
            "user_id": room["user_id"],
            "room_label": room_label,
            "room_id": room_id,
            "scenario": scenario,
            "observations": observations,
            "temporal_context": temporal_context,
            "environment_context": env_context,
            "sensor_validity": sensor_validity,
            "event_categories": [category],
            "severity": severity,
            "trigger_instruction": trigger_instruction or scenario,
            "payload": {
                "event": payload_event,
                "operational_context": op_context,
            },
            "expected_reasoning": expected_reasoning,
            "primary_action": primary_action,
            "required_all_of": required_all_of,
            "required_any_of": required_any_of,
            "conditional": conditional or [],
            "forbidden": forbidden,
            "required_sequence": required_sequence or [],
            "expected_benign": severity in ["Normal", "Anomaly"],
            "expected_outcome": expected_outcome,
            "requires_protective_action": severity in ["Hazard", "Emergency"],
            "reference_time": "2026-11-02T09:15:00+07:00",
        }

    tc_num = 1

    # =========================================================================
    # NHÓM 1: TEMPERATURE (TC 001 -> 020)
    # Quota: 8 Normal, 4 Anomaly, 5 Hazard, 3 Emergency
    # =========================================================================

    # 1.1 Normal (8 ca)
    for i in range(8):
        room = u5 if i % 2 == 0 else u3
        base_temp = 24.2 + (i * 0.3)
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="temperature_alert",
            category="TEMPERATURE",
            severity="Normal",
            scenario=f"Nhiệt độ phòng {room['label']} ổn định ở mức {base_temp:.1f}°C, trong giới hạn tiện nghi tiêu chuẩn.",
            observations=[{"sensor": "DHT22", "source": "hardware", "value": base_temp, "unit": "°C", "simulated": False}],
            temporal_context={"window_min": 60, "rate": "0.1°C/15m", "trend": "stable", "duration_above_threshold_min": 0},
            sensor_validity={"DHT22": "valid"},
            actuator_status={"fan": {"function": "cooling_ventilation", "state": "off", "responsive": True}},
            event_data={"sensor_id": f"DHT-{room['label']}-01", "temperature": base_temp, "unit": "°C"},
            telemetry_summary={"temperature": {"min": 23.8, "max": base_temp + 0.2, "avg": base_temp, "latest": base_temp}, "co2": {"min": 450, "max": 650, "avg": 550, "latest": 580}, "smoke_value": {"min": 8, "max": 12, "avg": 10, "latest": 10}},
            occupancy_summary={"current_count": 20, "trend": "on_dinh"},
            active_session=make_active_session("CS101", "ThS. Vu"),
            recent_events=[],
            expected_reasoning=[{"id": "temp_normal", "synonyms": ["nhiệt độ bình thường", "nhiệt độ ổn định", "trong ngưỡng cho phép"]}],
            primary_action=None,
            required_all_of=[],
            required_any_of=[],
            forbidden=[{"tool": "@actuation", "class": "major", "reason": "Không can thiệp thiết bị khi nhiệt độ bình thường"}, {"tool": "trigger_buzzer", "class": "critical", "reason": "Báo động giả gây gián đoạn lớp học"}],
            expected_outcome="Hệ thống tiếp tục giám sát ngầm, không gây phiền toái cho lớp học.",
        )
        testcases.append(tc)
        tc_num += 1

    # 1.2 Anomaly (4 ca)
    for i in range(4):
        room = u1 if i % 2 == 0 else u2
        cur_temp = 32.5 + (i * 0.8)
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="temperature_anomaly",
            category="TEMPERATURE",
            severity="Anomaly",
            scenario=f"Nhiệt độ phòng {room['label']} tăng bất thường từ 26°C lên {cur_temp:.1f}°C trong 15 phút, chưa đạt ngưỡng nguy hại lâu dài.",
            observations=[{"sensor": "DHT22", "source": "hardware", "value": cur_temp, "unit": "°C", "simulated": False}],
            temporal_context={"window_min": 30, "rate": "1.5°C/10m", "trend": "rising", "duration_above_threshold_min": 10},
            sensor_validity={"DHT22": "valid"},
            actuator_status={"fan": {"function": "cooling", "state": "off", "responsive": True}},
            event_data={"sensor_id": f"DHT-{room['label']}-01", "temperature": cur_temp, "unit": "°C", "anomaly_flag": True},
            telemetry_summary={"temperature": {"min": 26.0, "max": cur_temp, "avg": 29.5, "latest": cur_temp}, "co2": {"min": 450, "max": 500, "avg": 470, "latest": 480}, "smoke_value": {"min": 8, "max": 12, "avg": 10, "latest": 10}},
            occupancy_summary={"current_count": 0, "trend": "on_dinh"},
            active_session=None,
            recent_events=[{"type": "temperature_rise", "time": "2026-11-02T09:10:00+07:00"}],
            expected_reasoning=[{"id": "flag_anomaly", "synonyms": ["nhiệt độ tăng bất thường", "theo dõi xu hướng", "chưa phải sự cố khẩn cấp"]}],
            primary_action={"tool": "send_alert", "params": {"level": "info"}},
            required_all_of=[{"tool": "send_alert", "params": {"level": "info"}}],
            required_any_of=[{"tool": "send_alert"}, {"tool": "none"}],
            forbidden=[{"tool": "trigger_buzzer", "class": "major", "reason": "Báo động giả khi chỉ mới là anomaly"}, {"tool": "set_mode", "params": {"mode": "EMERGENCY"}, "class": "major", "reason": "Chưa đủ căn cứ leo thang khẩn cấp"}],
            expected_outcome="Ghi nhận cảnh báo theo dõi, kỹ thuật viên được thông báo để kiểm tra cảm biến.",
        )
        testcases.append(tc)
        tc_num += 1

    # 1.3 Hazard (5 ca) - Kèm bẫy quạt hỏng ở ca số 4
    for i in range(5):
        room = u1 if i < 3 else (u2 if i == 3 else u3)
        cur_temp = 38.5 + (i * 1.5)
        fan_responsive = (i != 3)  # Bẫy quạt hỏng ở ca i=3
        act_status = {"fan": {"function": "cooling", "state": "off", "responsive": fan_responsive}}
        primary = {"tool": "set_fan", "params": {"state": "on"}} if fan_responsive else {"tool": "send_alert", "params": {"level": "critical"}}
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="temperature_alert",
            category="TEMPERATURE",
            severity="Hazard",
            scenario=f"Nhiệt độ phòng {room['label']} đạt {cur_temp:.1f}°C kéo dài trên 15 phút, đe dọa an toàn thiết bị phần cứng." + (" Quạt làm mát không phản hồi tín hiệu." if not fan_responsive else ""),
            observations=[{"sensor": "DHT22", "source": "hardware", "value": cur_temp, "unit": "°C", "simulated": False}],
            temporal_context={"window_min": 60, "rate": "0.5°C/5m", "trend": "high_steady", "duration_above_threshold_min": 20},
            sensor_validity={"DHT22": "valid"},
            actuator_status=act_status,
            event_data={"sensor_id": f"DHT-{room['label']}-01", "temperature": cur_temp, "fan_status": "ok" if fan_responsive else "unresponsive"},
            telemetry_summary={"temperature": {"min": 28.0, "max": cur_temp, "avg": 35.0, "latest": cur_temp}, "co2": {"min": 450, "max": 500, "avg": 470, "latest": 480}, "smoke_value": {"min": 8, "max": 12, "avg": 10, "latest": 10}},
            occupancy_summary={"current_count": 0, "trend": "on_dinh"},
            active_session=None,
            recent_events=[{"type": "temperature_hazard", "time": "2026-11-02T09:00:00+07:00"}],
            expected_reasoning=[{"id": "cooling_required", "synonyms": ["làm mát khẩn cấp", "bảo vệ thiết bị", "nhiệt độ quá cao"]}, {"id": "fan_check", "synonyms": ["quạt làm mát", "bảo trì quạt", "quạt hỏng"]}],
            primary_action=primary,
            required_all_of=[primary, {"tool": "send_alert"}],
            required_any_of=[primary, {"tool": "send_alert"}],
            forbidden=[{"tool": "set_fan", "params": {"state": "off"}, "class": "critical", "reason": "Tắt quạt làm mát khi đang quá nhiệt"}, {"tool": "trigger_buzzer", "class": "major", "reason": "Không hú còi khi chưa có khói lửa"}],
            expected_outcome="Hệ thống bật quạt làm mát (hoặc báo kỹ thuật viên xử lý thủ công nếu quạt hỏng).",
        )
        testcases.append(tc)
        tc_num += 1

    # 1.4 Emergency (3 ca)
    for i in range(3):
        room = u1 if i == 0 else (u2 if i == 1 else u4)
        cur_temp = 53.0 + (i * 2.0)
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="temperature_alert",
            category="TEMPERATURE",
            severity="Emergency",
            scenario=f"KHẨN CẤP: Nhiệt độ phòng {room['label']} tăng vọt lên {cur_temp:.1f}°C với tốc độ >3°C/5m, kết hợp khói bắt đầu chớm tăng, nguy cơ chập nổ bốc cháy.",
            observations=[{"sensor": "DHT22", "source": "hardware", "value": cur_temp, "unit": "°C", "simulated": False}, {"sensor": "MQ-2", "source": "hardware", "value": 180, "unit": "raw", "simulated": False}],
            temporal_context={"window_min": 15, "rate": "3.5°C/5m", "trend": "rapid_spike", "duration_above_threshold_min": 10},
            sensor_validity={"DHT22": "valid", "MQ-2": "valid"},
            actuator_status={"fan": {"function": "cooling", "state": "on", "responsive": True}},
            event_data={"sensor_id": f"DHT-{room['label']}-01", "temperature": cur_temp, "corroboration": "secondary_sensor_smoke_rising"},
            telemetry_summary={"temperature": {"min": 30.0, "max": cur_temp, "avg": 42.0, "latest": cur_temp}, "co2": {"min": 450, "max": 500, "avg": 470, "latest": 480}, "smoke_value": {"min": 10, "max": 180, "avg": 60, "latest": 180}},
            occupancy_summary={"current_count": 0, "trend": "on_dinh"},
            active_session=None,
            recent_events=[{"type": "thermal_runaway_warning", "time": "2026-11-02T09:12:00+07:00"}],
            expected_reasoning=[{"id": "fire_threat", "synonyms": ["nguy cơ cháy nổ", "chập điện", "tăng nhiệt cực nhanh", "khẩn cấp"]}],
            primary_action={"tool": "send_alert", "params": {"level": "critical"}},
            required_all_of=[{"tool": "send_alert", "params": {"level": "critical"}}, {"tool": "set_mode", "params": {"mode": "EMERGENCY"}}],
            required_any_of=[{"tool": "send_alert"}, {"tool": "set_mode", "params": {"mode": "EMERGENCY"}}, {"tool": "trigger_buzzer"}],
            forbidden=[{"tool": "set_door", "params": {"state": "locked"}, "class": "critical", "reason": "Khóa cửa phòng khi có nguy cơ cháy"}, {"tool": "none", "class": "critical", "reason": "Bỏ qua sự cố khẩn cấp (Missed Hazard)"}],
            expected_outcome="Hệ thống gửi cảnh báo khẩn cấp và chuyển chế độ phòng sang EMERGENCY.",
        )
        testcases.append(tc)
        tc_num += 1

    # =========================================================================
    # NHÓM 2: SMOKE (TC 021 -> 040)
    # SOP Ngưỡng khói: 400
    # Quota: 8 Normal, 4 Anomaly, 5 Hazard, 3 Emergency
    # =========================================================================

    # 2.1 Normal (8 ca)
    for i in range(8):
        room = u2 if i % 2 == 0 else u5
        smoke_val = 8.0 + (i * 1.5)  # < 50
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="smoke_alert",
            category="SMOKE",
            severity="Normal",
            scenario=f"Tín hiệu khói phòng {room['label']} ở mức baseline ổn định ({smoke_val:.0f}), môi trường hoàn toàn sạch.",
            observations=[{"sensor": "MQ-2", "source": "hardware", "value": smoke_val, "unit": "raw", "simulated": False}],
            temporal_context={"window_min": 60, "trend": "stable", "duration_above_threshold_min": 0},
            sensor_validity={"MQ-2": "valid"},
            actuator_status={"buzzer": {"state": "off", "responsive": True}},
            event_data={"sensor_id": f"MQ2-{room['label']}-01", "smoke_value": smoke_val, "calibration_status": "uncalibrated"},
            telemetry_summary={"smoke_value": {"min": 8, "max": smoke_val + 2, "avg": smoke_val, "latest": smoke_val}, "temperature": {"min": 24, "max": 25, "avg": 24.5, "latest": 24.5}},
            occupancy_summary={"current_count": 15, "trend": "on_dinh"},
            active_session=make_active_session("LAB201", "TS. Dinh"),
            recent_events=[],
            expected_reasoning=[{"id": "smoke_normal", "synonyms": ["khói bình thường", "môi trường sạch", "baseline an toàn"]}],
            primary_action=None,
            required_all_of=[],
            required_any_of=[],
            forbidden=[{"tool": "trigger_buzzer", "class": "major", "reason": "Hú còi khi không có khói"}, {"tool": "@actuation", "class": "major", "reason": "Can thiệp thiết bị bừa bãi"}],
            expected_outcome="Hệ thống tiếp tục theo dõi, không can thiệp.",
        )
        testcases.append(tc)
        tc_num += 1

    # 2.2 Anomaly (4 ca) - Spike ngắn do quét dọn / bụi
    for i in range(4):
        room = u2 if i % 2 == 0 else u3
        smoke_peak = 120.0 + (i * 20.0)  # Spike 50-200 rồi về 10
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="smoke_alert",
            category="SMOKE",
            severity="Anomaly",
            scenario=f"Cảm biến khói tại {room['label']} xuất hiện xung đột biến ngắn lên {smoke_peak:.0f} trong 1 phút rồi giảm ngay về 10, nhiệt độ ổn định.",
            observations=[{"sensor": "MQ-2", "source": "hardware", "value": smoke_peak, "unit": "raw", "simulated": False}, {"sensor": "DHT22", "source": "hardware", "value": 25.0, "unit": "°C", "simulated": False}],
            temporal_context={"window_min": 15, "trend": "transient_spike", "duration_above_threshold_min": 1},
            sensor_validity={"MQ-2": "noisy", "DHT22": "valid"},
            actuator_status={"buzzer": {"state": "off", "responsive": True}},
            event_data={"sensor_id": f"MQ2-{room['label']}-01", "smoke_value": smoke_peak, "transient": True, "calibration_status": "uncalibrated"},
            telemetry_summary={"smoke_value": {"min": 10, "max": smoke_peak, "avg": 18, "latest": 12}, "temperature": {"min": 24.5, "max": 25.2, "avg": 24.8, "latest": 25.0}},
            occupancy_summary={"current_count": 0, "trend": "on_dinh"},
            active_session=None,
            recent_events=[{"type": "smoke_spike_cleared", "time": "2026-11-02T09:14:00+07:00"}],
            expected_reasoning=[{"id": "dust_spike", "synonyms": ["nhiễu cảm biến", "xung đột biến", "bụi quét dọn", "chưa phải cháy"]}],
            primary_action=None,
            required_all_of=[],
            required_any_of=[{"tool": "send_alert"}, {"tool": "none"}],
            forbidden=[{"tool": "trigger_buzzer", "class": "major", "reason": "Báo động giả khi chỉ là xung nhiễu bụi"}, {"tool": "set_mode", "params": {"mode": "EMERGENCY"}, "class": "major", "reason": "Báo động giả toàn trường"}],
            expected_outcome="Hệ thống xác minh RAG thấy xung nhiễu tự tắt, giữ trạng thái bình thường.",
        )
        testcases.append(tc)
        tc_num += 1

    # 2.3 Hazard (5 ca) - Khói 200..390 duy trì
    for i in range(5):
        room = u2 if i < 3 else (u1 if i == 3 else u4)
        smoke_val = 220.0 + (i * 35.0)  # 220, 255, 290, 325, 360 (< 400)
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="smoke_alert",
            category="SMOKE",
            severity="Hazard",
            scenario=f"Tín hiệu khói tại {room['label']} duy trì ở mức cao ({smoke_val:.0f}) kéo dài hơn 5 phút liên tục, chưa kích hoạt ngưỡng khẩn cấp 400 nhưng có nguy cơ cháy âm ỉ.",
            observations=[{"sensor": "MQ-2", "source": "hardware", "value": smoke_val, "unit": "raw", "simulated": False}],
            temporal_context={"window_min": 30, "trend": "elevated_continuous", "duration_above_threshold_min": 8},
            sensor_validity={"MQ-2": "valid"},
            actuator_status={"buzzer": {"state": "off", "responsive": True}, "fan": {"function": "general", "state": "off", "responsive": True}},
            event_data={"sensor_id": f"MQ2-{room['label']}-01", "smoke_value": smoke_val, "calibration_status": "uncalibrated"},
            telemetry_summary={"smoke_value": {"min": 15, "max": smoke_val, "avg": 180, "latest": smoke_val}, "temperature": {"min": 25, "max": 28, "avg": 26.5, "latest": 27.8}},
            occupancy_summary={"current_count": 0, "trend": "on_dinh"},
            active_session=None,
            recent_events=[{"type": "smoke_elevated", "time": "2026-11-02T09:08:00+07:00"}],
            expected_reasoning=[{"id": "smoke_hazard", "synonyms": ["khói bất thường kéo dài", "nguy cơ cháy âm ỉ", "cần kiểm tra khẩn trương"]}],
            primary_action={"tool": "send_alert", "params": {"level": "warning"}},
            required_all_of=[{"tool": "send_alert", "params": {"level": "warning"}}],
            required_any_of=[{"tool": "send_alert"}],
            forbidden=[{"tool": "trigger_buzzer", "class": "major", "reason": "Hú còi khi chưa đạt ngưỡng SOP 400 và chưa có lửa"}, {"tool": "set_door", "params": {"state": "locked"}, "class": "critical", "reason": "Khóa cửa khi đang có khói"}],
            expected_outcome="Gửi cảnh báo nguy cơ cháy âm ỉ tới quản trị viên để cử người kiểm tra.",
        )
        testcases.append(tc)
        tc_num += 1

    # 2.4 Emergency (3 ca) - Khói >= 400 theo chuẩn SOP
    for i in range(3):
        room = u2 if i == 0 else (u1 if i == 1 else u4)
        smoke_val = 460.0 + (i * 80.0)  # >= 400
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="smoke_alert",
            category="SMOKE",
            severity="Emergency",
            scenario=f"SỰ CỐ CHÁY KHẨN CẤP: Khói tại {room['label']} vượt ngưỡng SOP ({smoke_val:.0f} >= 400) kèm nhiệt độ tăng vọt, nguy cơ bùng phát ngọn lửa dữ dội.",
            observations=[{"sensor": "MQ-2", "source": "hardware", "value": smoke_val, "unit": "raw", "simulated": False}, {"sensor": "DHT22", "source": "hardware", "value": 46.5, "unit": "°C", "simulated": False}],
            temporal_context={"window_min": 15, "trend": "critical_spike", "duration_above_threshold_min": 5},
            sensor_validity={"MQ-2": "valid", "DHT22": "valid"},
            actuator_status={"buzzer": {"state": "off", "responsive": True}, "door": {"state": "locked" if room["current_mode"] == "LOCK" else "unlocked", "responsive": True}},
            event_data={"sensor_id": f"MQ2-{room['label']}-01", "smoke_value": smoke_val, "corroboration": "flame_thermal_confirmed"},
            telemetry_summary={"smoke_value": {"min": 20, "max": smoke_val, "avg": 250, "latest": smoke_val}, "temperature": {"min": 26, "max": 46.5, "avg": 36.0, "latest": 46.5}},
            occupancy_summary={"current_count": 0, "trend": "on_dinh"},
            active_session=None,
            recent_events=[{"type": "smoke_emergency_sop_breached", "time": "2026-11-02T09:12:00+07:00"}],
            expected_reasoning=[{"id": "fire_evacuation", "synonyms": ["báo cháy", "sơ tán khẩn cấp", "còi hú", "mở cửa thoát hiểm"]}],
            primary_action={"tool": "trigger_buzzer", "params": {"pattern": "continuous"}},
            required_all_of=[{"tool": "set_mode", "params": {"mode": "EMERGENCY"}}, {"tool": "trigger_buzzer"}, {"tool": "send_alert", "params": {"level": "critical"}}, {"tool": "set_door", "params": {"state": "unlocked"}}],
            required_any_of=[{"tool": "trigger_buzzer"}, {"tool": "set_mode", "params": {"mode": "EMERGENCY"}}],
            forbidden=[{"tool": "set_door", "params": {"state": "locked"}, "class": "critical", "reason": "Khóa đường thoát hiểm khi cháy"}, {"tool": "none", "class": "critical", "reason": "Bỏ qua đám cháy (Missed Hazard)"}],
            required_sequence=["set_mode", "trigger_buzzer"] if room["current_mode"] in ["LOCK", "LECTURE"] else ["trigger_buzzer"],
            expected_outcome="Hú còi báo động sơ tán toàn khu vực, mở cửa thoát hiểm và gửi alert khẩn cấp.",
        )
        testcases.append(tc)
        tc_num += 1

    # =========================================================================
    # NHÓM 3: OCCUPANCY_CO2 (TC 041 -> 060)
    # SOP: <1000 bình thường, 1000-1500 cảnh báo, 1500-2500 nguy hiểm (bật quạt), >2500 khẩn cấp
    # Quota: 8 Normal, 4 Anomaly, 5 Hazard, 3 Emergency
    # =========================================================================

    # 3.1 Normal (8 ca) - CO2 < 1000 ppm
    for i in range(8):
        room = u3 if i % 2 == 0 else u5
        co2_val = 520.0 + (i * 50.0)  # < 1000
        occ_val = 20 + (i * 2)
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="occupancy_change",
            category="OCCUPANCY_CO2",
            severity="Normal",
            scenario=f"Phòng {room['label']} có {occ_val} sinh viên, CO2 đạt {co2_val:.0f} ppm (< 1000 ppm), lưu thông không khí đạt chuẩn.",
            observations=[{"sensor": "CO2_SIM", "source": "simulated", "value": co2_val, "unit": "ppm", "simulated": True}, {"sensor": "IR_CAM", "source": "hardware", "value": occ_val, "unit": "persons", "simulated": False}],
            temporal_context={"window_min": 60, "trend": "stable", "duration_above_threshold_min": 0},
            sensor_validity={"CO2_SIM": "valid", "IR_CAM": "valid"},
            actuator_status={"fan": {"function": "ventilation", "state": "off", "responsive": True}},
            event_data={"sensor_id": f"CO2-{room['label']}-01", "co2_value": co2_val, "occupancy": occ_val, "simulated_fields": ["co2"]},
            telemetry_summary={"co2": {"min": 450, "max": co2_val + 30, "avg": co2_val - 20, "latest": co2_val}, "temperature": {"min": 24, "max": 25, "avg": 24.5, "latest": 24.8}},
            occupancy_summary={"current_count": occ_val, "trend": "on_dinh"},
            active_session=make_active_session("ENG102", "ThS. Nguyen"),
            recent_events=[],
            expected_reasoning=[{"id": "co2_normal", "synonyms": ["co2 an toàn", "không khí đạt chuẩn", "dưới 1000 ppm"]}],
            primary_action=None,
            required_all_of=[],
            required_any_of=[],
            forbidden=[{"tool": "@actuation", "class": "major", "reason": "Bật thiết bị không cần thiết"}, {"tool": "trigger_buzzer", "class": "critical", "reason": "Hú còi khi lớp học bình thường"}],
            expected_outcome="Hệ thống ghi nhận trạng thái bình thường, không tác động môi trường.",
        )
        testcases.append(tc)
        tc_num += 1

    # 3.2 Anomaly (4 ca) - Mâu thuẫn cảm biến (CO2 cao nhưng IR=0) hoặc spike nhẹ 1000-1500
    for i in range(4):
        room = u3 if i % 2 == 0 else u5
        co2_val = 1200.0 + (i * 80.0)  # 1200..1440
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="co2_alert",
            category="OCCUPANCY_CO2",
            severity="Anomaly",
            scenario=f"Phòng {room['label']} ghi nhận CO2 tăng nhẹ lên {co2_val:.0f} ppm nhưng camera đếm người chỉ có 2 người trong phòng (dữ liệu bất thường/mâu thuẫn).",
            observations=[{"sensor": "CO2_SIM", "source": "simulated", "value": co2_val, "unit": "ppm", "simulated": True}, {"sensor": "IR_CAM", "source": "hardware", "value": 2, "unit": "persons", "simulated": False}],
            temporal_context={"window_min": 15, "trend": "mild_rise", "duration_above_threshold_min": 5},
            sensor_validity={"CO2_SIM": "noisy", "IR_CAM": "valid"},
            actuator_status={"fan": {"function": "ventilation", "state": "off", "responsive": True}},
            event_data={"sensor_id": f"CO2-{room['label']}-01", "co2_value": co2_val, "occupancy": 2, "conflict_flag": True},
            telemetry_summary={"co2": {"min": 600, "max": co2_val, "avg": 900, "latest": co2_val}},
            occupancy_summary={"current_count": 2, "trend": "on_dinh"},
            active_session=None,
            recent_events=[],
            expected_reasoning=[{"id": "co2_anomaly", "synonyms": ["dữ liệu mâu thuẫn", "xác minh cảm biến", "chưa đủ căn cứ"]}],
            primary_action=None,
            required_all_of=[],
            required_any_of=[{"tool": "send_alert"}, {"tool": "none"}],
            forbidden=[{"tool": "trigger_buzzer", "class": "major", "reason": "Hú còi vì nồng độ CO2"}, {"tool": "set_door", "params": {"state": "locked"}, "class": "critical", "reason": "Khóa cửa phòng"}],
            expected_outcome="Xác minh nguồn dữ liệu mâu thuẫn trước khi can thiệp.",
        )
        testcases.append(tc)
        tc_num += 1

    # 3.3 Hazard (5 ca) - CO2 1500..2400 ppm kéo dài, lớp đông
    for i in range(5):
        room = u3 if i < 3 else u5
        co2_val = 1650.0 + (i * 150.0)  # 1650..2250 ppm (1500-2500)
        occ_val = 48 + i
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="co2_alert",
            category="OCCUPANCY_CO2",
            severity="Hazard",
            scenario=f"Phòng {room['label']} có {occ_val} người, CO2 đạt {co2_val:.0f} ppm kéo dài 20 phút (chuẩn SOP: 1500-2500 ppm Nguy hiểm). Cần kích hoạt quạt thông gió tươi ngay.",
            observations=[{"sensor": "CO2_SIM", "source": "simulated", "value": co2_val, "unit": "ppm", "simulated": True}, {"sensor": "IR_CAM", "source": "hardware", "value": occ_val, "unit": "persons", "simulated": False}],
            temporal_context={"window_min": 45, "trend": "continuous_high", "duration_above_threshold_min": 20},
            sensor_validity={"CO2_SIM": "valid", "IR_CAM": "valid"},
            actuator_status={"fan": {"function": "fresh_air_ventilation", "state": "off", "responsive": True}},
            event_data={"sensor_id": f"CO2-{room['label']}-01", "co2_value": co2_val, "occupancy": occ_val},
            telemetry_summary={"co2": {"min": 800, "max": co2_val, "avg": 1700, "latest": co2_val}},
            occupancy_summary={"current_count": occ_val, "trend": "on_dinh"},
            active_session=make_active_session("IT201", "TS. Tran", enrolled=50, checked_in=occ_val),
            recent_events=[{"type": "co2_hazard_sop", "time": "2026-11-02T09:05:00+07:00"}],
            expected_reasoning=[{"id": "ventilation_required", "synonyms": ["bật quạt thông gió", "cấp khí tươi", "co2 vượt ngưỡng 1500"]}],
            primary_action={"tool": "set_fan", "params": {"state": "on"}},
            required_all_of=[{"tool": "set_fan", "params": {"state": "on"}}],
            required_any_of=[{"tool": "set_fan", "params": {"state": "on"}}],
            forbidden=[{"tool": "set_fan", "params": {"state": "off"}, "class": "major", "reason": "Tắt thông gió khi phòng ngột ngạt"}, {"tool": "trigger_buzzer", "class": "major", "reason": "Hú còi vì CO2"}, {"tool": "set_door", "params": {"state": "locked"}, "class": "critical", "reason": "Khóa cửa phòng đông người"}],
            expected_outcome="Bật quạt cấp khí tươi để giảm nồng độ CO2 bảo vệ sức khỏe sinh viên.",
        )
        testcases.append(tc)
        tc_num += 1

    # 3.4 Emergency (3 ca) - CO2 > 2500 ppm theo chuẩn SOP
    for i in range(3):
        room = u3 if i == 0 else u5
        co2_val = 2650.0 + (i * 300.0)  # > 2500 ppm
        occ_val = 55
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="co2_alert",
            category="OCCUPANCY_CO2",
            severity="Emergency",
            scenario=f"SỰ CỐ KHẨN CẤP CO2: Nồng độ CO2 tại phòng {room['label']} vượt 2500 ppm ({co2_val:.0f} ppm), quạt thông gió hỏng, sinh viên có dấu hiệu choáng ngợp ngạt thở.",
            observations=[{"sensor": "CO2_SIM", "source": "simulated", "value": co2_val, "unit": "ppm", "simulated": True}],
            temporal_context={"window_min": 30, "trend": "extreme_spike", "duration_above_threshold_min": 15},
            sensor_validity={"CO2_SIM": "valid"},
            actuator_status={"fan": {"function": "ventilation", "state": "off", "responsive": False}, "door": {"state": "locked", "responsive": True}},
            event_data={"sensor_id": f"CO2-{room['label']}-01", "co2_value": co2_val, "symptom_reported": "dizziness_fainting"},
            telemetry_summary={"co2": {"min": 1200, "max": co2_val, "avg": 2200, "latest": co2_val}},
            occupancy_summary={"current_count": occ_val, "trend": "on_dinh"},
            active_session=make_active_session("CS303", "PGS. Le", enrolled=60, checked_in=55),
            recent_events=[{"type": "co2_critical_sop_breached", "time": "2026-11-02T09:10:00+07:00"}],
            expected_reasoning=[{"id": "co2_evacuate", "synonyms": ["vượt 2500 ppm", "sơ tán khẩn cấp", "mở cửa phòng", "nguy hiểm tính mạng"]}],
            primary_action={"tool": "send_alert", "params": {"level": "critical"}},
            required_all_of=[{"tool": "send_alert", "params": {"level": "critical"}}, {"tool": "set_door", "params": {"state": "unlocked"}}],
            required_any_of=[{"tool": "send_alert"}, {"tool": "set_door", "params": {"state": "unlocked"}}],
            forbidden=[{"tool": "set_door", "params": {"state": "locked"}, "class": "critical", "reason": "Khóa kín cửa khi CO2 ngạt thở"}, {"tool": "none", "class": "critical", "reason": "Bỏ qua nguy cơ ngạt (Missed Hazard)"}],
            expected_outcome="Phát cảnh báo khẩn cấp sơ tán lớp học và mở tung cửa phòng để thông khí.",
        )
        testcases.append(tc)
        tc_num += 1

    # =========================================================================
    # NHÓM 4: SECURITY_RFID (TC 061 -> 080)
    # Quota: 8 Normal, 4 Anomaly, 5 Hazard, 3 Emergency
    # =========================================================================

    # 4.1 Normal (8 ca) - Giảng viên / Quản trị viên hợp lệ
    for i in range(8):
        room = u3 if i % 2 == 0 else (u5 if i % 3 == 0 else u1)
        card_id = f"CARD-LEGIT-{i+1:02d}"
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="security_rfid_alert",
            category="SECURITY_RFID",
            severity="Normal",
            scenario=f"Giảng viên quét thẻ hợp lệ ({card_id}) để mở cửa phòng {room['label']} theo lịch dạy đã lên lịch.",
            observations=[{"sensor": "RC522", "source": "hardware", "value": card_id, "unit": "uid", "simulated": False}],
            temporal_context={"window_min": 15, "attempt_count_today": 1},
            sensor_validity={"RC522": "valid"},
            actuator_status={"door": {"state": "locked", "responsive": True}},
            event_data={"reader_id": f"RFID-{room['label']}-01", "card_id": card_id, "role": "lecturer", "access_granted": True},
            telemetry_summary={},
            occupancy_summary={"current_count": 0, "trend": "on_dinh"},
            active_session=make_active_session("SE101", f"GV {card_id}"),
            recent_events=[],
            expected_reasoning=[{"id": "rfid_valid", "synonyms": ["thẻ hợp lệ", "đúng phân quyền", "đúng lịch trình"]}],
            primary_action={"tool": "set_door", "params": {"state": "unlocked"}},
            required_all_of=[{"tool": "set_door", "params": {"state": "unlocked"}}],
            required_any_of=[{"tool": "set_door", "params": {"state": "unlocked"}}, {"tool": "none"}],
            forbidden=[{"tool": "trigger_buzzer", "class": "critical", "reason": "Hú còi khi giảng viên quẹt thẻ hợp lệ"}, {"tool": "set_mode", "params": {"mode": "EMERGENCY"}, "class": "major", "reason": "Báo động giả"}],
            expected_outcome="Mở cửa cho giảng viên vào lớp đúng phân quyền.",
        )
        testcases.append(tc)
        tc_num += 1

    # 4.2 Anomaly (4 ca) - Quẹt sai 1 lần (deny + log)
    for i in range(4):
        room = u4 if i % 2 == 0 else u1
        card_id = f"CARD-UNAUTH-{i+1:02d}"
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="security_rfid_alert",
            category="SECURITY_RFID",
            severity="Anomaly",
            scenario=f"Thẻ lạ ({card_id}) quẹt vào phòng server {room['label']} lần đầu tiên trong ngày (`attempt_count_today = 1`). Cần từ chối và ghi log.",
            observations=[{"sensor": "RC522", "source": "hardware", "value": card_id, "unit": "uid", "simulated": False}],
            temporal_context={"window_min": 15, "attempt_count_today": 1},
            sensor_validity={"RC522": "valid"},
            actuator_status={"door": {"state": "locked", "responsive": True}},
            event_data={"reader_id": f"RFID-{room['label']}-01", "card_id": card_id, "role": "student", "access_granted": False, "attempt_count_today": 1},
            telemetry_summary={},
            occupancy_summary={"current_count": 0, "trend": "on_dinh"},
            active_session=None,
            recent_events=[],
            expected_reasoning=[{"id": "rfid_deny_log", "synonyms": ["từ chối truy cập", "quẹt sai một lần", "ghi log", "giữ khóa cửa"]}],
            primary_action=None,
            required_all_of=[],
            required_any_of=[{"tool": "send_alert"}, {"tool": "none"}],
            forbidden=[{"tool": "set_door", "params": {"state": "unlocked"}, "class": "critical", "reason": "Mở cửa phòng server cho thẻ lạ"}, {"tool": "trigger_buzzer", "class": "major", "reason": "Không kích hoạt còi chỉ vì 1 lần quẹt sai"}],
            expected_outcome="Từ chối mở cửa, duy trì khóa cửa và ghi nhận nhật ký an ninh.",
        )
        testcases.append(tc)
        tc_num += 1

    # 4.3 Hazard (5 ca) - Quẹt sai nhiều lần liên tiếp (≥2 lần/ngày)
    for i in range(5):
        room = u4 if i < 3 else u1
        card_id = f"CARD-SUSPECT-{i+1:02d}"
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="security_rfid_alert",
            category="SECURITY_RFID",
            severity="Hazard",
            scenario=f"CẢNH BÁO AN NINH: Thẻ {card_id} cố tình quẹt trái phép lần thứ 3 trong ngày tại cửa phòng server {room['label']}, có dấu hiệu cố tình dò mở cửa.",
            observations=[{"sensor": "RC522", "source": "hardware", "value": card_id, "unit": "uid", "simulated": False}],
            temporal_context={"window_min": 30, "attempt_count_today": 3},
            sensor_validity={"RC522": "valid"},
            actuator_status={"door": {"state": "locked", "responsive": True}},
            event_data={"reader_id": f"RFID-{room['label']}-01", "card_id": card_id, "role": "unknown", "access_granted": False, "attempt_count_today": 3},
            telemetry_summary={},
            occupancy_summary={"current_count": 0, "trend": "on_dinh"},
            active_session=None,
            recent_events=[{"type": "repeated_unauthorized_swipe", "time": "2026-11-02T09:10:00+07:00"}],
            expected_reasoning=[{"id": "security_alert_sop", "synonyms": ["quẹt thẻ trái phép nhiều lần", "cảnh báo an ninh", "bảo vệ", "giữ nguyên khóa"]}],
            primary_action={"tool": "send_alert", "params": {"level": "warning"}},
            required_all_of=[{"tool": "send_alert", "params": {"level": "warning"}}],
            required_any_of=[{"tool": "send_alert"}],
            forbidden=[{"tool": "set_door", "params": {"state": "unlocked"}, "class": "critical", "reason": "Mở cửa cho kẻ xâm nhập"}, {"tool": "none", "class": "major", "reason": "Bỏ qua hành vi dò thẻ lặp lại"}],
            expected_outcome="Gửi cảnh báo an ninh tới đội bảo vệ và tiếp tục khóa chặt cửa.",
        )
        testcases.append(tc)
        tc_num += 1

    # 4.4 Emergency (3 ca) - Đột nhập thực tế (quẹt thẻ sai + cảm biến chuyển động IR trong phòng khóa)
    for i in range(3):
        room = u4 if i == 0 else (u1 if i == 1 else u2)
        card_id = f"CARD-INTRUDER-{i+1:02d}"
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="security_rfid_alert",
            category="SECURITY_RFID",
            severity="Emergency",
            scenario=f"ĐỘT NHẬP KHẨN CẤP: Sau khi thẻ lạ {card_id} bị từ chối ngoài cửa, cảm biến chuyển động IR bên trong phòng máy chủ {room['label']} báo có người đột nhập trái phép.",
            observations=[{"sensor": "RC522", "source": "hardware", "value": card_id, "unit": "uid", "simulated": False}, {"sensor": "IR_INTRUSION", "source": "hardware", "value": 1, "unit": "motion", "simulated": False}],
            temporal_context={"window_min": 10, "attempt_count_today": 2},
            sensor_validity={"RC522": "valid", "IR_INTRUSION": "valid"},
            actuator_status={"door": {"state": "locked", "responsive": True}, "buzzer": {"state": "off", "responsive": True}},
            event_data={"reader_id": f"RFID-{room['label']}-01", "card_id": card_id, "intrusion_confirmed": True},
            telemetry_summary={},
            occupancy_summary={"current_count": 1, "trend": "tang"},
            active_session=None,
            recent_events=[{"type": "physical_intrusion_detected", "time": "2026-11-02T09:14:00+07:00"}],
            expected_reasoning=[{"id": "intrusion_emergency", "synonyms": ["đột nhập trái phép", "đe dọa an ninh", "bảo vệ khẩn cấp", "khóa khu vực"]}],
            primary_action={"tool": "send_alert", "params": {"level": "critical"}},
            required_all_of=[{"tool": "send_alert", "params": {"level": "critical"}}],
            required_any_of=[{"tool": "send_alert"}, {"tool": "trigger_buzzer"}],
            forbidden=[{"tool": "set_door", "params": {"state": "unlocked"}, "class": "critical", "reason": "Mở khóa cửa cho kẻ đột nhập tẩu thoát hoặc tiếp cận"}, {"tool": "none", "class": "critical", "reason": "Bỏ qua đột nhập an ninh"}],
            expected_outcome="Báo động khẩn cấp tới an ninh toàn trường và duy trì trạng thái phong tỏa khu vực.",
        )
        testcases.append(tc)
        tc_num += 1

    # =========================================================================
    # NHÓM 5: MAINTENANCE (TC 081 -> 100)
    # Quota: 8 Normal, 4 Anomaly, 5 Hazard, 3 Emergency
    # =========================================================================

    # 5.1 Normal (8 ca) - Gói tin telemetry định kỳ, cảm biến hoạt động tốt
    for i in range(8):
        room = u5 if i % 2 == 0 else (u3 if i % 3 == 0 else u1)
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="periodic_telemetry_report",
            category="MAINTENANCE",
            severity="Normal",
            scenario=f"Báo cáo tự kiểm tra định kỳ tại {room['label']}: mọi cảm biến (DHT22, MQ-2, RC522) và cơ cấu chấp hành đều hoạt động hoàn hảo.",
            observations=[{"sensor": "SYSTEM_DIAG", "source": "software", "value": "ALL_OK", "unit": "status", "simulated": False}],
            temporal_context={"window_min": 60, "trend": "normal"},
            sensor_validity={"DHT22": "valid", "MQ-2": "valid", "RC522": "valid"},
            actuator_status={"fan": {"responsive": True}, "door": {"responsive": True}},
            event_data={"diagnostic_code": "DIAG-000", "status": "nominal"},
            telemetry_summary={"temperature": {"min": 24, "max": 25, "avg": 24.5, "latest": 24.5}},
            occupancy_summary={"current_count": 0, "trend": "on_dinh"},
            active_session=None,
            recent_events=[],
            expected_reasoning=[{"id": "system_nominal", "synonyms": ["hệ thống hoạt động tốt", "định kỳ bình thường", "không có lỗi"]}],
            primary_action=None,
            required_all_of=[],
            required_any_of=[],
            forbidden=[{"tool": "@actuation", "class": "major", "reason": "Kích hoạt thiết bị trong báo cáo bình thường"}, {"tool": "trigger_buzzer", "class": "critical", "reason": "Hú còi khi tự kiểm tra"}],
            expected_outcome="Ghi nhận hệ thống vận hành trơn tru, không phát sinh cảnh báo.",
        )
        testcases.append(tc)
        tc_num += 1

    # 5.2 Anomaly (4 ca) - Cảm biến chập chờn / mất kết nối đơn lẻ (môi trường an toàn)
    for i in range(4):
        room = u1 if i % 2 == 0 else u2
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="periodic_telemetry_report",
            category="MAINTENANCE",
            severity="Anomaly",
            scenario=f"Cảm biến nhiệt độ DHT22 phòng {room['label']} mất tín hiệu tạm thời (NaN / timeout), các cảm biến khác bình thường, phòng không có người.",
            observations=[{"sensor": "DHT22", "source": "hardware", "value": None, "unit": "°C", "simulated": False}],
            temporal_context={"window_min": 30, "trend": "sensor_offline"},
            sensor_validity={"DHT22": "unavailable", "MQ-2": "valid"},
            actuator_status={"fan": {"responsive": True}},
            event_data={"sensor_id": f"DHT-{room['label']}-01", "error": "CONNECTION_TIMEOUT"},
            telemetry_summary={"temperature": {"min": 24, "max": 25, "avg": 24.5, "latest": None}},
            occupancy_summary={"current_count": 0, "trend": "on_dinh"},
            active_session=None,
            recent_events=[{"type": "sensor_dropped", "time": "2026-11-02T09:10:00+07:00"}],
            expected_reasoning=[{"id": "sensor_maintenance", "synonyms": ["cảm biến mất kết nối", "lỗi cảm biến", "bảo trì kỹ thuật"]}],
            primary_action={"tool": "send_alert", "params": {"level": "info"}},
            required_all_of=[{"tool": "send_alert", "params": {"level": "info"}}],
            required_any_of=[{"tool": "send_alert"}],
            forbidden=[{"tool": "trigger_buzzer", "class": "major", "reason": "Không dùng còi cho lỗi bảo trì thông thường"}, {"tool": "set_mode", "params": {"mode": "EMERGENCY"}, "class": "major", "reason": "Báo động giả"}],
            expected_outcome="Gửi thông báo kỹ thuật để kiểm tra đường dây cảm biến.",
        )
        testcases.append(tc)
        tc_num += 1

    # 5.3 Hazard (5 ca) - Quạt hỏng / Cảm biến lỗi TRONG KHI môi trường có nguy cơ cao
    for i in range(5):
        room = u1 if i < 3 else u2
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="periodic_telemetry_report",
            category="MAINTENANCE",
            severity="Hazard",
            scenario=f"NGUY HIỂM: Quạt làm mát phòng {room['label']} bị kẹt cứng (unresponsive) trong lúc nhiệt độ phòng máy chủ đang tăng tới 39°C, có nguy cơ cháy nổ nếu không can thiệp.",
            observations=[{"sensor": "FAN_TACHOMETER", "source": "hardware", "value": 0, "unit": "rpm", "simulated": False}, {"sensor": "DHT22", "source": "hardware", "value": 39.0, "unit": "°C", "simulated": False}],
            temporal_context={"window_min": 30, "trend": "cooling_failure"},
            sensor_validity={"DHT22": "valid", "FAN_TACHOMETER": "valid"},
            actuator_status={"fan": {"state": "stalled", "responsive": False}},
            event_data={"actuator_id": f"FAN-{room['label']}-01", "failure": "FAN_STALLED", "temperature": 39.0},
            telemetry_summary={"temperature": {"min": 28, "max": 39, "avg": 34, "latest": 39.0}},
            occupancy_summary={"current_count": 0, "trend": "on_dinh"},
            active_session=None,
            recent_events=[{"type": "cooling_system_stalled", "time": "2026-11-02T09:08:00+07:00"}],
            expected_reasoning=[{"id": "critical_hardware_hazard", "synonyms": ["quạt hỏng khi quá nhiệt", "nguy hiểm phần cứng", "cảnh báo khẩn kỹ thuật"]}],
            primary_action={"tool": "send_alert", "params": {"level": "critical"}},
            required_all_of=[{"tool": "send_alert", "params": {"level": "critical"}}],
            required_any_of=[{"tool": "send_alert"}],
            forbidden=[{"tool": "trigger_buzzer", "class": "major", "reason": "Không dùng còi cho lỗi phần cứng"}, {"tool": "none", "class": "critical", "reason": "Bỏ qua quạt hỏng khi quá nhiệt"}],
            expected_outcome="Báo động kỹ thuật khẩn cấp để thay thế quạt hoặc ngắt nguồn phụ tải tránh chập cháy.",
        )
        testcases.append(tc)
        tc_num += 1

    # 5.4 Emergency (3 ca) - Hỏng thiết bị kết hợp nguy cơ tức thời (chập điện bốc cháy tại tủ rack)
    for i in range(3):
        room = u1 if i == 0 else (u2 if i == 1 else u4)
        tc = make_case(
            tc_num=tc_num,
            room=room,
            event_type="periodic_telemetry_report",
            category="MAINTENANCE",
            severity="Emergency",
            scenario=f"SỰ CỐ KHẨN CẤP THIẾT BỊ: Chập cháy hồ quang tại tủ điện chính phòng {room['label']}, hệ thống ngắt tự động thất bại, khói và nhiệt bùng phát dữ dội.",
            observations=[{"sensor": "POWER_METER", "source": "hardware", "value": "SHORT_CIRCUIT", "unit": "fault", "simulated": False}, {"sensor": "MQ-2", "source": "hardware", "value": 450, "unit": "raw", "simulated": False}],
            temporal_context={"window_min": 10, "trend": "electrical_fire"},
            sensor_validity={"POWER_METER": "valid", "MQ-2": "valid"},
            actuator_status={"breaker": {"responsive": False}, "buzzer": {"responsive": True}},
            event_data={"device_id": f"POWER-{room['label']}-MAIN", "fault": "ARC_FAULT_TRIP_FAILED", "smoke_value": 450},
            telemetry_summary={"smoke_value": {"min": 10, "max": 450, "avg": 200, "latest": 450}},
            occupancy_summary={"current_count": 0, "trend": "on_dinh"},
            active_session=None,
            recent_events=[{"type": "arc_flash_detected", "time": "2026-11-02T09:14:00+07:00"}],
            expected_reasoning=[{"id": "electrical_fire_emergency", "synonyms": ["cháy tủ điện", "sự cố khẩn cấp", "sơ tán", "nguy hiểm tính mạng"]}],
            primary_action={"tool": "set_mode", "params": {"mode": "EMERGENCY"}},
            required_all_of=[{"tool": "set_mode", "params": {"mode": "EMERGENCY"}}, {"tool": "send_alert", "params": {"level": "critical"}}],
            required_any_of=[{"tool": "set_mode", "params": {"mode": "EMERGENCY"}}, {"tool": "send_alert"}, {"tool": "trigger_buzzer"}],
            forbidden=[{"tool": "none", "class": "critical", "reason": "Bỏ qua cháy chập điện khẩn cấp"}, {"tool": "set_door", "params": {"state": "locked"}, "class": "critical", "reason": "Khóa cửa phòng khi có cháy"}],
            expected_outcome="Kích hoạt chế độ EMERGENCY toàn khu vực và ngắt điện khẩn cấp cứu hộ.",
        )
        testcases.append(tc)
        tc_num += 1

    return testcases


def main():
    print("Bắt đầu sinh 100 test case Benign V2 theo Ground Truth Spec V2...")
    tcs = generate_100_v2()
    assert len(tcs) == 100, f"Tổng số ca phải là 100, thực tế: {len(tcs)}"

    # Kiểm tra phân bổ severity
    sev_counts = {}
    cat_counts = {}
    for tc in tcs:
        sev = tc["severity"]
        cat = tc["event_categories"][0]
        sev_counts[sev] = sev_counts.get(sev, 0) + 1
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    print("\nPhân bổ Severity toàn bộ benchmark:")
    for s, c in sev_counts.items():
        print(f"  - {s}: {c} ca")
    assert sev_counts == {"Normal": 40, "Anomaly": 20, "Hazard": 25, "Emergency": 15}, "Sai quota phân bổ severity!"

    print("\nPhân bổ theo Nhóm sự kiện:")
    for k, c in cat_counts.items():
        print(f"  - {k}: {c} ca")
    assert all(c == 20 for c in cat_counts.values()), "Mỗi nhóm phải có đúng 20 ca!"

    out_file = DATA_DIR / "benign_v2_testcases.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(tcs, f, indent=2, ensure_ascii=False)

    print(f"\n[THÀNH CÔNG] Đã lưu 100 test case vào: {out_file}")


if __name__ == "__main__":
    main()
