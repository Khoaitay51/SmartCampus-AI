"""
tests/fixtures/mock_store_data.py
---------------------------------
Centralized Mock Store Data cho tất cả RAG tools.

Tổ chức theo SCENARIO — mỗi scenario chứa đầy đủ dữ liệu cho MỌI tool
mà Agent có thể gọi, để Agent luôn có dữ liệu thực tế khi suy luận.

Mỗi scenario gồm:
  - trigger_payload: EventPayload + OperationalContext gửi cho Agent
  - rag_store: dict[tool_name] -> response data cho tool đó
  - expected_outcome: mô tả kết quả mong đợi (để verify agent reasoning)

Cách dùng:
  from tests.fixtures.mock_store_data import SCENARIOS, get_rag_response
  scenario = SCENARIOS["fire_real_37c"]
  response = get_rag_response(scenario, "get_telemetry", {"room_id": "...", "metric": "temperature"})
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


# ===========================================================================
# ROOM IDs cố định cho từng scenario (dễ trace/debug)
# ===========================================================================
ROOM_A101 = "00000000-0000-0000-0000-000000000101"
ROOM_B202 = "00000000-0000-0000-0000-000000000202"
ROOM_C305 = "00000000-0000-0000-0000-000000000305"
ROOM_A204 = "00000000-0000-0000-0000-000000000204"
ROOM_LAB301 = "00000000-0000-0000-0000-000000000301"


# ===========================================================================
# SCENARIO 1: CHÁY THẬT — Nhiệt độ 37°C + khói tăng liên tục
# Backend phát hiện temperature=37, vượt ngưỡng → trigger TEMPERATURE_ANOMALY
# Agent phải gọi get_telemetry, get_predictions (bắt buộc) → thấy trend rising
# mạnh + dự báo tiếp tục tăng → đề xuất set_fan ON hoặc send_alert
# ===========================================================================
SCENARIO_FIRE_REAL = {
    "id": "fire_real_37c",
    "label": "🔥 Cháy thật — Nhiệt độ 37°C + trend tăng mạnh liên tục",
    "description": (
        "Backend phát hiện temperature=37°C vượt ngưỡng 34°C. "
        "Telemetry 30 phút qua cho thấy nhiệt tăng liên tục từ 28→37°C. "
        "Dự báo EWMA tiếp tục tăng lên 39.5°C. Khói cũng bắt đầu tăng nhẹ. "
        "Agent PHẢI kết luận đây là sự cố thật và đề xuất hành động."
    ),
    "trigger_payload": {
        "event": {
            "event_id": str(uuid4()),
            "event_type": "temperature_anomaly",
            "room_id": ROOM_A101,
            "timestamp": "2026-09-27T09:00:00+07:00",
            "event_data": {
                "temperature": 37.0,
                "humidity": 45.0,
                "co2": 1850,
                "smoke_value": 180.0,
                "trigger": "threshold_exceeded",
                "threshold": 34.0,
            },
        },
        "context": {
            "room": {
                "room_id": ROOM_A101,
                "room_name": "Phòng A101 — Giảng đường lớn",
                "room_type": "lecture_hall",
                "current_mode": "LECTURE",
                "smoke_state": "normal",
            },
            "telemetry_summary": {
                "window_start": "2026-09-27T08:30:00+07:00",
                "window_end": "2026-09-27T09:00:00+07:00",
                "temperature": {"min": 28.0, "max": 37.0, "avg": 33.2, "latest": 37.0},
                "humidity": {"min": 40.0, "max": 55.0, "avg": 47.5, "latest": 45.0},
                "co2": {"min": 900.0, "max": 1850.0, "avg": 1350.0, "latest": 1850.0},
                "smoke_value": {"min": 10.0, "max": 180.0, "avg": 65.0, "latest": 180.0},
                "air_quality": {"min": 30.0, "max": 70.0, "avg": 48.0, "latest": 32.0},
            },
            "occupancy": {"current_count": 42, "total_in": 45, "total_out": 3, "trend": "stable"},
            "active_session": {
                "session_id": str(uuid4()),
                "class_code": "EE301",
                "lecturer_name": "PGS. Trần Văn B",
                "enrolled_count": 45,
                "checked_in_count": 42,
                "started_at": "2026-09-27T07:30:00+07:00",
                "attendance_deadline": "2026-09-27T07:45:00+07:00",
                "is_exam": False,
            },
            "recent_events": [
                {"type": "temperature_anomaly", "time": "2026-09-27T08:45:00+07:00", "extra": {"temperature": 35.2}},
                {"type": "temperature_anomaly", "time": "2026-09-27T08:55:00+07:00", "extra": {"temperature": 36.5}},
            ],
        },
    },
    "rag_store": {
        # --- get_telemetry: nhiệt tăng liên tục 30 phút ---
        "get_telemetry": {
            "room_id": ROOM_A101,
            "metric": "temperature",
            "window": "1h",
            "latest": 37.0,
            "avg": 33.2,
            "min": 28.0,
            "max": 37.0,
            "trend": "sharp_increase",
            "samples_count": 30,
            "data_points": [
                {"time": "08:30", "value": 28.0},
                {"time": "08:35", "value": 29.1},
                {"time": "08:40", "value": 30.5},
                {"time": "08:45", "value": 32.0},
                {"time": "08:50", "value": 34.2},
                {"time": "08:55", "value": 36.5},
                {"time": "09:00", "value": 37.0},
            ],
            "analysis": (
                "Nhiệt độ tăng đều đặn và mạnh từ 28.0°C lên 37.0°C trong 30 phút (+9°C). "
                "Tốc độ tăng 0.3°C/phút — bất thường, không phải do đông người thông thường. "
                "Kết hợp CO2 tăng mạnh (1850ppm) và smoke_value bắt đầu tăng."
            ),
        },
        # --- get_predictions: dự báo tiếp tục tăng vọt ---
        "get_predictions": {
            "room_id": ROOM_A101,
            "metric": "temperature",
            "horizon": "15m",
            "current_value": 37.0,
            "predicted_value": 39.5,
            "trend": "rising",
            "confidence": 0.94,
            "model": "EWMA-v2",
            "analysis": (
                "CẢNH BÁO EWMA: Nhiệt độ dự báo sẽ tiếp tục tăng vọt lên 39.5°C "
                "trong 15 phút tới nếu không can thiệp. Tốc độ tăng hiện tại 0.3°C/phút."
            ),
        },
        # --- compare_rooms: chỉ phòng này bất thường ---
        "compare_rooms": {
            "metric": "temperature",
            "window": "1h",
            "comparisons": [
                {"room_id": ROOM_A101, "value": 37.0, "status": "anomaly"},
                {"room_id": ROOM_B202, "value": 25.5, "status": "normal"},
                {"room_id": ROOM_C305, "value": 26.0, "status": "normal"},
            ],
            "analysis": "Chỉ phòng A101 bất thường (37°C). Các phòng lân cận bình thường (25-26°C). Sự cố cục bộ.",
        },
        # --- get_schedule: đang có lớp ---
        "get_schedule": {
            "room_id": ROOM_A101,
            "date": "2026-09-27",
            "active_session": {
                "class_code": "EE301",
                "subject": "Điện tử công suất",
                "lecturer": "PGS. Trần Văn B",
                "start": "07:30",
                "end": "11:30",
                "room_mode": "LECTURE",
            },
        },
        # --- get_room_history: 2 lần cảnh báo nhiệt gần đây ---
        "get_room_history": {
            "room_id": ROOM_A101,
            "hours": 1,
            "transitions": [
                {"timestamp": "2026-09-27T07:30:00+07:00", "mode": "LECTURE", "trigger": "class_start"},
                {"timestamp": "2026-09-27T08:45:00+07:00", "mode": "LECTURE", "trigger": "temp_warning_35.2"},
                {"timestamp": "2026-09-27T08:55:00+07:00", "mode": "LECTURE", "trigger": "temp_warning_36.5"},
            ],
            "recent_decisions": [
                {
                    "event_type": "temperature_anomaly",
                    "decision": "skip",
                    "reason": "Nhiệt tăng nhẹ, chưa đủ ngưỡng hành động",
                    "timestamp": "2026-09-27T08:45:00+07:00",
                },
                {
                    "event_type": "temperature_anomaly",
                    "decision": "skip",
                    "reason": "Nhiệt 36.5°C, backoff — lần retry sau 08:45, chưa đủ ngưỡng cuối",
                    "timestamp": "2026-09-27T08:55:00+07:00",
                },
            ],
            "note": "2 cảnh báo nhiệt trong 15 phút gần đây, trend tăng liên tục. Chưa có hành động can thiệp nào.",
        },
        # --- search_history: tìm incident tương tự ---
        "search_history": {
            "query": "temperature_anomaly nhiệt độ tăng vọt",
            "results": [
                {
                    "event_type": "temperature_anomaly",
                    "action_taken": "set_fan",
                    "parameters": {"room_id": ROOM_A101, "state": "on"},
                    "outcome": "Bật quạt thông gió, nhiệt giảm về 27°C sau 15 phút.",
                    "similarity": 0.93,
                },
            ],
        },
        # --- get_attendance: lớp đang học ---
        "get_attendance": {
            "room_id": ROOM_A101,
            "class_code": "EE301",
            "enrolled_count": 45,
            "checked_in_count": 42,
            "attendance_rate": 0.93,
            "status": "ongoing",
        },
    },
    "expected_outcome": {
        "skip": False,
        "expected_tool": "set_fan",
        "min_confidence": 0.7,
        "urgency": "high",
        "reasoning": (
            "Nhiệt tăng liên tục 28→37°C trong 30 phút, dự báo tiếp tục lên 39.5°C, "
            "chỉ phòng A101 bất thường, đang có 42 người trong phòng → phải can thiệp."
        ),
    },
}


# ===========================================================================
# SCENARIO 2: NHIỄU — Nhiệt độ 37°C nhưng chỉ 1 điểm đột biến rồi ổn định
# Agent phải gọi tool, thấy trend stable/giảm → kết luận là nhiễu → SKIP
# ===========================================================================
SCENARIO_TEMP_NOISE = {
    "id": "temp_noise_37c_spike",
    "label": "📊 Nhiễu — Nhiệt 37°C nhưng chỉ 1 spike rồi tự giảm",
    "description": (
        "Backend phát hiện temperature=37°C nhưng telemetry cho thấy đây chỉ là "
        "1 spike ngắn rồi tự giảm về 29°C. Dự báo ổn định. "
        "Agent PHẢI kết luận là nhiễu sensor và skip."
    ),
    "trigger_payload": {
        "event": {
            "event_id": str(uuid4()),
            "event_type": "temperature_anomaly",
            "room_id": ROOM_B202,
            "timestamp": "2026-09-27T10:15:00+07:00",
            "event_data": {
                "temperature": 37.0,
                "humidity": 60.0,
                "co2": 650,
                "smoke_value": 0.0,
                "trigger": "threshold_exceeded",
                "threshold": 34.0,
            },
        },
        "context": {
            "room": {
                "room_id": ROOM_B202,
                "room_name": "Lab B202 — Vật lý",
                "room_type": "laboratory",
                "current_mode": "LECTURE",
                "smoke_state": "normal",
            },
            "telemetry_summary": {
                "window_start": "2026-09-27T09:45:00+07:00",
                "window_end": "2026-09-27T10:15:00+07:00",
                "temperature": {"min": 25.0, "max": 37.0, "avg": 27.5, "latest": 29.0},
                "humidity": {"min": 55.0, "max": 65.0, "avg": 60.0, "latest": 60.0},
                "co2": {"min": 500.0, "max": 700.0, "avg": 600.0, "latest": 650.0},
                "smoke_value": {"min": 0.0, "max": 2.0, "avg": 0.5, "latest": 0.0},
                "air_quality": {"min": 80.0, "max": 95.0, "avg": 88.0, "latest": 90.0},
            },
            "occupancy": {"current_count": 15, "total_in": 16, "total_out": 1, "trend": "stable"},
            "active_session": {
                "session_id": str(uuid4()),
                "class_code": "PHY201",
                "lecturer_name": "TS. Lê Văn C",
                "enrolled_count": 20,
                "checked_in_count": 15,
                "started_at": "2026-09-27T09:30:00+07:00",
                "attendance_deadline": "2026-09-27T09:45:00+07:00",
                "is_exam": False,
            },
            "recent_events": [],
        },
    },
    "rag_store": {
        "get_telemetry": {
            "room_id": ROOM_B202,
            "metric": "temperature",
            "window": "1h",
            "latest": 29.0,
            "avg": 27.5,
            "min": 25.0,
            "max": 37.0,
            "trend": "spike_then_stable",
            "samples_count": 25,
            "data_points": [
                {"time": "09:45", "value": 26.0},
                {"time": "09:50", "value": 26.2},
                {"time": "09:55", "value": 26.5},
                {"time": "10:00", "value": 37.0},
                {"time": "10:05", "value": 31.0},
                {"time": "10:10", "value": 29.5},
                {"time": "10:15", "value": 29.0},
            ],
            "analysis": (
                "Nhiệt độ có 1 spike đột biến lên 37°C lúc 10:00 rồi giảm nhanh "
                "về 29°C trong 15 phút. Đây có thể do lỗi sensor tạm thời hoặc "
                "nguồn nhiệt cục bộ đã được loại bỏ. Xu hướng hiện tại: ổn định."
            ),
        },
        "get_predictions": {
            "room_id": ROOM_B202,
            "metric": "temperature",
            "horizon": "15m",
            "current_value": 29.0,
            "predicted_value": 28.5,
            "trend": "stable",
            "confidence": 0.88,
            "model": "EWMA-v2",
            "analysis": "Dự báo nhiệt độ ổn định quanh 28.5-29°C trong 15 phút tới. Spike đã qua.",
        },
        "compare_rooms": {
            "metric": "temperature",
            "window": "1h",
            "comparisons": [
                {"room_id": ROOM_B202, "value": 29.0, "status": "normal"},
                {"room_id": ROOM_A101, "value": 26.5, "status": "normal"},
            ],
        },
        "get_schedule": {
            "room_id": ROOM_B202,
            "date": "2026-09-27",
            "active_session": {
                "class_code": "PHY201",
                "subject": "Thí nghiệm Vật lý đại cương",
                "lecturer": "TS. Lê Văn C",
                "start": "09:30",
                "end": "11:30",
                "room_mode": "LECTURE",
            },
        },
        "get_room_history": {
            "room_id": ROOM_B202,
            "hours": 1,
            "transitions": [
                {"timestamp": "2026-09-27T09:30:00+07:00", "mode": "LECTURE", "trigger": "class_start"},
            ],
            "recent_decisions": [],
            "note": "Không có sự kiện bất thường nào trong 1h qua ngoài spike nhiệt vừa xảy ra.",
        },
        "search_history": {
            "query": "temperature spike đột biến",
            "results": [
                {
                    "event_type": "temperature_anomaly",
                    "action_taken": "skip",
                    "parameters": {},
                    "outcome": "Spike sensor tạm thời, tự ổn định sau 10 phút. Không cần can thiệp.",
                    "similarity": 0.89,
                },
            ],
        },
        "get_attendance": {
            "room_id": ROOM_B202,
            "class_code": "PHY201",
            "enrolled_count": 20,
            "checked_in_count": 15,
            "attendance_rate": 0.75,
            "status": "ongoing",
        },
    },
    "expected_outcome": {
        "skip": True,
        "expected_tool": None,
        "max_confidence": 0.5,
        "reasoning": (
            "Chỉ 1 spike rồi giảm nhanh, dự báo ổn định, "
            "quá khứ có pattern tương tự đã skip → nhiễu sensor."
        ),
    },
}


# ===========================================================================
# SCENARIO 3: KHÓI PHÁT HIỆN — Smoke tăng liên tục, lần đầu
# Agent gọi get_telemetry (smoke) + get_room_history → thấy tăng liên tục,
# lần đầu → đề xuất trigger_buzzer (cảnh báo sớm)
# ===========================================================================
SCENARIO_SMOKE_REAL = {
    "id": "smoke_first_spike_real",
    "label": "🚨 Khói thật — Smoke tăng liên tục, lần đầu tiên",
    "description": (
        "Cảm biến MQ2 phát hiện smoke tăng từ 60→415 trong 3 phút. "
        "Lần đầu tiên trong 24h. Nhiệt phòng ổn định 26°C (chưa có cháy rõ). "
        "Agent phải đề xuất trigger_buzzer (cảnh báo sớm)."
    ),
    "trigger_payload": {
        "event": {
            "event_id": str(uuid4()),
            "event_type": "smoke_detected",
            "room_id": ROOM_LAB301,
            "timestamp": "2026-09-27T14:30:00+07:00",
            "event_data": {
                "smoke_value": 415.0,
                "smoke_state": "suspected",
                "mq2_raw": 520,
                "trigger": "smoke_threshold_exceeded",
                "threshold": 400,
            },
        },
        "context": {
            "room": {
                "room_id": ROOM_LAB301,
                "room_name": "Lab 301 — Hóa hữu cơ",
                "room_type": "laboratory",
                "current_mode": "SUSPECTED",
                "smoke_state": "suspected",
            },
            "telemetry_summary": {
                "window_start": "2026-09-27T14:15:00+07:00",
                "window_end": "2026-09-27T14:30:00+07:00",
                "temperature": {"min": 25.5, "max": 26.5, "avg": 26.0, "latest": 26.2},
                "humidity": {"min": 55.0, "max": 62.0, "avg": 58.0, "latest": 60.0},
                "co2": {"min": 600.0, "max": 800.0, "avg": 700.0, "latest": 780.0},
                "smoke_value": {"min": 40.0, "max": 415.0, "avg": 180.0, "latest": 415.0},
                "air_quality": {"min": 45.0, "max": 80.0, "avg": 62.0, "latest": 48.0},
            },
            "occupancy": {"current_count": 12, "total_in": 14, "total_out": 2, "trend": "stable"},
            "active_session": {
                "session_id": str(uuid4()),
                "class_code": "CHEM301",
                "lecturer_name": "TS. Nguyễn Thị D",
                "enrolled_count": 15,
                "checked_in_count": 12,
                "started_at": "2026-09-27T13:30:00+07:00",
                "attendance_deadline": "2026-09-27T13:45:00+07:00",
                "is_exam": False,
            },
            "recent_events": [],
        },
    },
    "rag_store": {
        "get_telemetry": {
            "room_id": ROOM_LAB301,
            "metric": "smoke",
            "window": "15m",
            "latest": 415.0,
            "avg": 180.0,
            "min": 40.0,
            "max": 415.0,
            "trend": "sharp_spike",
            "samples_count": 15,
            "data_points": [
                {"time": "14:15", "value": 40},
                {"time": "14:18", "value": 55},
                {"time": "14:21", "value": 90},
                {"time": "14:24", "value": 160},
                {"time": "14:27", "value": 310},
                {"time": "14:30", "value": 415},
            ],
            "analysis": (
                "Chỉ số khói MQ2 tăng liên tục và mạnh từ 40→415 trong 15 phút. "
                "Không có dấu hiệu giảm. Nhiệt phòng vẫn ổn định 26°C."
            ),
        },
        "get_room_history": {
            "room_id": ROOM_LAB301,
            "hours": 6,
            "smoke_events_past_24h": 0,
            "current_state": "SUSPECTED",
            "transitions": [
                {"timestamp": "2026-09-27T13:30:00+07:00", "mode": "LECTURE", "trigger": "class_start"},
            ],
            "note": "24h qua không ghi nhận bất kỳ sự kiện khói nào. Đây là lần đầu tiên cảm biến MQ2 chạm ngưỡng.",
        },
        "get_predictions": {
            "room_id": ROOM_LAB301,
            "metric": "smoke",
            "horizon": "15m",
            "current_value": 415.0,
            "predicted_value": 620.0,
            "trend": "rising",
            "confidence": 0.91,
            "model": "EWMA-v2",
            "analysis": "Dự báo smoke tiếp tục tăng lên 620 trong 15 phút tới nếu không can thiệp.",
        },
        "compare_rooms": {
            "metric": "smoke",
            "window": "15m",
            "comparisons": [
                {"room_id": ROOM_LAB301, "value": 415.0, "status": "anomaly"},
                {"room_id": ROOM_B202, "value": 5.0, "status": "normal"},
            ],
            "analysis": "Chỉ Lab 301 có smoke bất thường. Các phòng lân cận bình thường.",
        },
        "search_history": {
            "query": "smoke_detected smoke tăng đột biến",
            "results": [],
        },
        "get_schedule": {
            "room_id": ROOM_LAB301,
            "date": "2026-09-27",
            "active_session": {
                "class_code": "CHEM301",
                "subject": "Thí nghiệm Hóa hữu cơ",
                "lecturer": "TS. Nguyễn Thị D",
                "start": "13:30",
                "end": "17:30",
                "room_mode": "LECTURE",
            },
        },
        "get_attendance": {
            "room_id": ROOM_LAB301,
            "class_code": "CHEM301",
            "enrolled_count": 15,
            "checked_in_count": 12,
            "attendance_rate": 0.80,
            "status": "ongoing",
        },
    },
    "expected_outcome": {
        "skip": False,
        "expected_tool": "trigger_buzzer",
        "min_confidence": 0.65,
        "urgency": "high",
        "reasoning": (
            "Smoke tăng liên tục 40→415, lần đầu trong 24h, dự báo tiếp tục tăng. "
            "Phòng lab hóa chất → nguy cơ cao. Cần cảnh báo sớm."
        ),
    },
}


# ===========================================================================
# SCENARIO 4: KHÓI NHIỄU — Smoke spike 1 lần rồi giảm (nấu ăn gần đó)
# Agent phải kết luận là nhiễu → skip
# ===========================================================================
SCENARIO_SMOKE_NOISE = {
    "id": "smoke_noise_cooking",
    "label": "🍳 Khói nhiễu — Spike từ bếp nấu rồi tự giảm",
    "description": (
        "Smoke spike lên 450 rồi giảm nhanh về 80 trong 5 phút. "
        "Nhiệt ổn định. Lịch sử có 2 lần tương tự (đều là nấu ăn gần đó). "
        "Agent phải skip."
    ),
    "trigger_payload": {
        "event": {
            "event_id": str(uuid4()),
            "event_type": "smoke_detected",
            "room_id": ROOM_C305,
            "timestamp": "2026-09-27T12:05:00+07:00",
            "event_data": {
                "smoke_value": 450.0,
                "smoke_state": "suspected",
                "mq2_raw": 560,
                "trigger": "smoke_threshold_exceeded",
                "threshold": 400,
            },
        },
        "context": {
            "room": {
                "room_id": ROOM_C305,
                "room_name": "Phòng C305 — Tự học",
                "room_type": "study_room",
                "current_mode": "SELF_STUDY",
                "smoke_state": "suspected",
            },
            "telemetry_summary": {
                "window_start": "2026-09-27T11:50:00+07:00",
                "window_end": "2026-09-27T12:05:00+07:00",
                "temperature": {"min": 25.0, "max": 26.0, "avg": 25.5, "latest": 25.8},
                "humidity": {"min": 55.0, "max": 62.0, "avg": 58.0, "latest": 60.0},
                "co2": {"min": 400.0, "max": 600.0, "avg": 500.0, "latest": 550.0},
                "smoke_value": {"min": 10.0, "max": 450.0, "avg": 120.0, "latest": 80.0},
                "air_quality": {"min": 60.0, "max": 90.0, "avg": 75.0, "latest": 82.0},
            },
            "occupancy": {"current_count": 3, "total_in": 5, "total_out": 2, "trend": "stable"},
            "active_session": None,
            "recent_events": [],
        },
    },
    "rag_store": {
        "get_telemetry": {
            "room_id": ROOM_C305,
            "metric": "smoke",
            "window": "15m",
            "latest": 80.0,
            "avg": 120.0,
            "min": 10.0,
            "max": 450.0,
            "trend": "spike_then_decreasing",
            "samples_count": 10,
            "data_points": [
                {"time": "11:50", "value": 15},
                {"time": "11:55", "value": 20},
                {"time": "12:00", "value": 450},
                {"time": "12:02", "value": 280},
                {"time": "12:05", "value": 80},
            ],
            "analysis": (
                "Smoke spike lên 450 lúc 12:00 rồi giảm nhanh về 80 trong 5 phút. "
                "Nhiệt phòng ổn định 25-26°C. Đặc trưng nhiễu từ nguồn bên ngoài."
            ),
        },
        "get_room_history": {
            "room_id": ROOM_C305,
            "hours": 6,
            "smoke_events_past_24h": 2,
            "current_state": "SELF_STUDY",
            "transitions": [
                {"timestamp": "2026-09-27T08:00:00+07:00", "mode": "SELF_STUDY", "trigger": "schedule"},
            ],
            "recent_decisions": [
                {
                    "event_type": "smoke_detected",
                    "decision": "skip",
                    "reason": "Smoke spike từ bếp ăn tầng dưới, tự giảm sau 5 phút.",
                    "timestamp": "2026-09-26T12:10:00+07:00",
                },
                {
                    "event_type": "smoke_detected",
                    "decision": "skip",
                    "reason": "Khói bay vào từ cửa sổ, giảm nhanh. Không cần hành động.",
                    "timestamp": "2026-09-25T11:55:00+07:00",
                },
            ],
            "note": "Phòng C305 đã có 2 lần smoke spike tương tự trong 48h qua, đều tự giảm và được skip.",
        },
        "get_predictions": {
            "room_id": ROOM_C305,
            "metric": "smoke",
            "horizon": "15m",
            "current_value": 80.0,
            "predicted_value": 45.0,
            "trend": "decreasing",
            "confidence": 0.86,
            "model": "EWMA-v2",
            "analysis": "Dự báo smoke tiếp tục giảm về mức bình thường (~45) trong 15 phút.",
        },
        "compare_rooms": {
            "metric": "smoke",
            "window": "15m",
            "comparisons": [
                {"room_id": ROOM_C305, "value": 80.0, "status": "normal"},
                {"room_id": ROOM_A101, "value": 5.0, "status": "normal"},
            ],
        },
        "search_history": {
            "query": "smoke_detected smoke tăng đột biến",
            "results": [
                {
                    "event_type": "smoke_detected",
                    "action_taken": "skip",
                    "parameters": {},
                    "outcome": "Smoke spike từ bếp ăn tầng dưới, tự giảm. False alarm.",
                    "similarity": 0.94,
                },
            ],
        },
        "get_schedule": {
            "room_id": ROOM_C305,
            "date": "2026-09-27",
            "active_session": None,
            "classes_today": [],
            "note": "Phòng tự học, không có lịch cố định.",
        },
        "get_attendance": {
            "room_id": ROOM_C305,
            "class_code": None,
            "enrolled_count": 0,
            "checked_in_count": 0,
            "attendance_rate": 0,
            "status": "no_session",
            "note": "Phòng tự học, không có lớp chính thức. 3 người có mặt là tự học tự do, không điểm danh.",
        },
    },
    "expected_outcome": {
        "skip": True,
        "expected_tool": None,
        "max_confidence": 0.5,
        "reasoning": (
            "Spike rồi giảm nhanh, lịch sử có 2 lần tương tự đều skip, "
            "dự báo tiếp tục giảm → nhiễu (nấu ăn/cửa sổ)."
        ),
    },
}


# ===========================================================================
# SCENARIO 5: RFID LẠ BAN ĐÊM — Thẻ không xác định lúc 22h
# ===========================================================================
SCENARIO_RFID_NIGHT = {
    "id": "rfid_unknown_night",
    "label": "🔐 RFID lạ ban đêm — Thẻ không xác định lúc 22h",
    "description": (
        "Thẻ RFID không có trong hệ thống quẹt cửa phòng A204 lúc 22:00. "
        "Phòng đã khóa từ 17:30. Không có lịch học buổi tối."
    ),
    "trigger_payload": {
        "event": {
            "event_id": str(uuid4()),
            "event_type": "rfid_unknown",
            "room_id": ROOM_A204,
            "timestamp": "2026-09-27T22:00:00+07:00",
            "event_data": {
                "card_uid": "B7:E3:22:1A",
                "reader_id": "door-main",
                "scan_result": "unknown",
            },
        },
        "context": {
            "room": {
                "room_id": ROOM_A204,
                "room_name": "Phòng A204",
                "room_type": "lecture_hall",
                "current_mode": "LOCK",
                "smoke_state": "normal",
            },
            "telemetry_summary": {
                "window_start": "2026-09-27T21:45:00+07:00",
                "window_end": "2026-09-27T22:00:00+07:00",
                "temperature": {"min": 24.0, "max": 25.0, "avg": 24.5, "latest": 24.5},
                "humidity": {"min": 55.0, "max": 60.0, "avg": 57.0, "latest": 58.0},
                "co2": {"min": 350.0, "max": 420.0, "avg": 380.0, "latest": 400.0},
                "smoke_value": {"min": 0.0, "max": 2.0, "avg": 0.5, "latest": 0.0},
                "air_quality": {"min": 90.0, "max": 98.0, "avg": 95.0, "latest": 96.0},
            },
            "occupancy": {"current_count": 0, "total_in": 0, "total_out": 0, "trend": "empty"},
            "active_session": None,
            "recent_events": [],
        },
    },
    "rag_store": {
        "get_schedule": {
            "room_id": ROOM_A204,
            "date": "2026-09-27",
            "classes_today": [
                {"class_code": "CS101", "start": "07:30", "end": "11:30", "status": "completed"},
                {"class_code": "MATH201", "start": "13:30", "end": "17:30", "status": "completed"},
            ],
            "active_session": None,
            "note": "Phòng A204 không có lịch học buổi tối sau 17:30.",
        },
        "get_room_history": {
            "room_id": ROOM_A204,
            "hours": 24,
            "current_state": "LOCK",
            "transitions": [
                {"timestamp": "2026-09-27T13:30:00+07:00", "mode": "LECTURE", "trigger": "class_start"},
                {"timestamp": "2026-09-27T17:30:00+07:00", "mode": "LOCK", "trigger": "class_end_and_lock"},
            ],
            "note": "Phòng đã đóng cửa và chuyển sang LOCK từ 17:30. Không có người ra vào hợp lệ từ đó.",
        },
        "get_attendance": {
            "room_id": ROOM_A204,
            "class_code": None,
            "enrolled_count": 0,
            "checked_in_count": 0,
            "attendance_rate": 0,
            "status": "no_active_session",
        },
        "search_history": {
            "query": "rfid_unknown thẻ lạ quẹt cửa",
            "results": [],
        },
        "get_telemetry": {
            "room_id": ROOM_A204,
            "metric": "temperature",
            "window": "1h",
            "latest": 24.5,
            "avg": 24.5,
            "min": 24.0,
            "max": 25.0,
            "trend": "stable",
            "samples_count": 12,
        },
        "get_predictions": {
            "room_id": ROOM_A204,
            "metric": "temperature",
            "horizon": "15m",
            "current_value": 24.5,
            "predicted_value": 24.3,
            "trend": "stable",
            "confidence": 0.95,
        },
        "compare_rooms": {
            "metric": "temperature",
            "window": "1h",
            "comparisons": [
                {"room_id": ROOM_A204, "value": 24.5, "status": "normal"},
            ],
        },
    },
    "expected_outcome": {
        "skip": False,
        "expected_tool": "send_alert",
        "min_confidence": 0.6,
        "urgency": "high",
        "reasoning": (
            "Thẻ lạ quẹt ngoài giờ, phòng đã khóa, không có lịch → đáng nghi. "
            "Gửi cảnh báo cho bảo vệ."
        ),
    },
}


# ===========================================================================
# SCENARIO 6: FSM CONFLICT — Nhiệt 35°C trong phòng THI (EXAM mode)
# Agent phải biết trigger_buzzer BỊ CẤM trong EXAM → dùng send_alert
# ===========================================================================
ROOM_D401 = "00000000-0000-0000-0000-000000000401"

SCENARIO_EXAM_TEMP_FSM = {
    "id": "exam_temp_fsm_conflict",
    "label": "📝 FSM Conflict — Nhiệt 35°C trong phòng thi, cấm trigger_buzzer",
    "description": (
        "Phòng D401 đang tổ chức thi giữa kỳ (EXAM mode). Nhiệt độ tăng lên 35°C. "
        "trigger_buzzer bị CẤM trong EXAM (làm gián đoạn bài thi). "
        "Agent phải nhận ra FSM conflict và chọn send_alert thay thế."
    ),
    "trigger_payload": {
        "event": {
            "event_id": str(uuid4()),
            "event_type": "temperature_anomaly",
            "room_id": ROOM_D401,
            "timestamp": "2026-09-28T09:30:00+07:00",
            "event_data": {
                "temperature": 35.2,
                "humidity": 58.0,
                "co2": 1200,
                "smoke_value": 8.0,
                "trigger": "threshold_exceeded",
                "threshold": 34.0,
            },
        },
        "context": {
            "room": {
                "room_id": ROOM_D401,
                "room_name": "Phòng D401 — Phòng thi",
                "room_type": "lecture_hall",
                "current_mode": "EXAM",
                "smoke_state": "normal",
            },
            "telemetry_summary": {
                "window_start": "2026-09-28T09:00:00+07:00",
                "window_end": "2026-09-28T09:30:00+07:00",
                "temperature": {"min": 28.0, "max": 35.2, "avg": 31.5, "latest": 35.2},
                "humidity": {"min": 55.0, "max": 62.0, "avg": 58.0, "latest": 58.0},
                "co2": {"min": 600.0, "max": 1200.0, "avg": 900.0, "latest": 1200.0},
                "smoke_value": {"min": 2.0, "max": 12.0, "avg": 6.0, "latest": 8.0},
                "air_quality": {"min": 60.0, "max": 85.0, "avg": 72.0, "latest": 65.0},
            },
            "occupancy": {"current_count": 38, "total_in": 40, "total_out": 2, "trend": "stable"},
            "active_session": {
                "session_id": str(uuid4()),
                "class_code": "CS301_EXAM",
                "lecturer_name": "PGS. Nguyễn Văn A",
                "enrolled_count": 40,
                "checked_in_count": 38,
                "started_at": "2026-09-28T08:00:00+07:00",
                "attendance_deadline": "2026-09-28T08:15:00+07:00",
                "is_exam": True,
            },
            "recent_events": [],
        },
    },
    "rag_store": {
        "get_telemetry": {
            "room_id": ROOM_D401,
            "metric": "temperature",
            "window": "1h",
            "latest": 35.2,
            "avg": 31.5,
            "min": 28.0,
            "max": 35.2,
            "trend": "increasing",
            "samples_count": 18,
            "data_points": [
                {"time": "09:00", "value": 28.0},
                {"time": "09:05", "value": 29.2},
                {"time": "09:10", "value": 30.5},
                {"time": "09:15", "value": 31.8},
                {"time": "09:20", "value": 33.1},
                {"time": "09:25", "value": 34.4},
                {"time": "09:30", "value": 35.2},
            ],
            "analysis": (
                "Nhiệt độ tăng đều +1.2°C/5 phút từ 28→35.2°C trong 30 phút. "
                "Phòng đông người (38 sv đang thi) và điều hòa có thể chưa đủ công suất."
            ),
        },
        "get_predictions": {
            "room_id": ROOM_D401,
            "metric": "temperature",
            "horizon": "15m",
            "current_value": 35.2,
            "predicted_value": 37.0,
            "trend": "rising",
            "confidence": 0.87,
            "model": "EWMA-v2",
            "analysis": "Dự báo nhiệt tiếp tục tăng lên 37°C trong 15 phút tới nếu không can thiệp.",
        },
        "get_schedule": {
            "room_id": ROOM_D401,
            "date": "2026-09-28",
            "active_session": {
                "class_code": "CS301_EXAM",
                "subject": "Thi giữa kỳ — Thuật toán nâng cao",
                "lecturer": "PGS. Nguyễn Văn A",
                "start": "08:00",
                "end": "10:00",
                "room_mode": "EXAM",
                "is_exam": True,
            },
        },
        "get_room_history": {
            "room_id": ROOM_D401,
            "hours": 1,
            "transitions": [
                {"timestamp": "2026-09-28T07:50:00+07:00", "mode": "EXAM", "trigger": "exam_start"},
            ],
            "recent_decisions": [],
            "note": "Phòng đang trong buổi thi giữa kỳ. Không có hành động can thiệp nào trước đó.",
        },
        "compare_rooms": {
            "metric": "temperature",
            "window": "1h",
            "comparisons": [
                {"room_id": ROOM_D401, "value": 35.2, "status": "anomaly"},
                {"room_id": ROOM_A101, "value": 26.0, "status": "normal"},
            ],
            "analysis": "Chỉ D401 bất thường. Sự cố cục bộ, không phải hệ thống.",
        },
        "search_history": {
            "query": "temperature_anomaly exam mode nhiệt tăng",
            "results": [
                {
                    "event_type": "temperature_anomaly",
                    "action_taken": "send_alert",
                    "parameters": {"room_id": ROOM_D401, "level": "warning"},
                    "outcome": "Giám thị đã điều chỉnh điều hòa, nhiệt giảm sau 10 phút.",
                    "similarity": 0.88,
                },
            ],
        },
        "get_attendance": {
            "room_id": ROOM_D401,
            "class_code": "CS301_EXAM",
            "enrolled_count": 40,
            "checked_in_count": 38,
            "attendance_rate": 0.95,
            "status": "exam_in_progress",
        },
    },
    "expected_outcome": {
        "skip": False,
        "expected_tool": "send_alert",
        "min_confidence": 0.70,
        "urgency": "high",
        "reasoning": (
            "Nhiệt tăng rõ ràng (28→35.2°C), dự báo tiếp tục. "
            "Phòng đang thi EXAM → trigger_buzzer BỊ CẤM (FSM permission matrix). "
            "Agent PHẢI chọn send_alert thông báo giám thị, không được dùng còi."
        ),
    },
}


# ===========================================================================
# SCENARIO 7: EMPTY DATA — Cảm biến báo 40°C nhưng get_telemetry trả rỗng
# DB mất kết nối / sensor đứt dây → Agent phải thận trọng, không kết luận vội
# Expected: skip=False → send_alert mức warning để kỹ thuật viên kiểm tra
# ===========================================================================
ROOM_E502 = "00000000-0000-0000-0000-000000000502"

SCENARIO_SENSOR_DEAD = {
    "id": "temp_sensor_dead_empty_data",
    "label": "🔌 Dữ liệu rỗng — Cảm biến báo 40°C nhưng DB trả rỗng (sensor đứt)",
    "description": (
        "Backend nhận signal temperature=40°C vượt ngưỡng từ phòng E502. "
        "Tuy nhiên khi Agent gọi get_telemetry, DB trả về mảng rỗng — cảm biến "
        "có thể đã bị ngắt kết nối. Agent KHÔNG được coi dữ liệu rỗng là 'an toàn', "
        "phải hạ confidence và gửi cảnh báo kỹ thuật."
    ),
    "trigger_payload": {
        "event": {
            "event_id": str(uuid4()),
            "event_type": "temperature_anomaly",
            "room_id": ROOM_E502,
            "timestamp": "2026-09-28T14:00:00+07:00",
            "event_data": {
                "temperature": 40.0,
                "humidity": None,
                "co2": None,
                "smoke_value": None,
                "trigger": "threshold_exceeded",
                "threshold": 34.0,
                "sensor_status": "unstable",
            },
        },
        "context": {
            "room": {
                "room_id": ROOM_E502,
                "room_name": "Phòng E502 — Phòng thực hành máy tính",
                "room_type": "computer_lab",
                "current_mode": "SELF_STUDY",
                "smoke_state": "unknown",
            },
            "telemetry_summary": {
                "window_start": "2026-09-28T13:45:00+07:00",
                "window_end": "2026-09-28T14:00:00+07:00",
                "temperature": {"min": None, "max": None, "avg": None, "latest": 40.0},
                "humidity": {"min": None, "max": None, "avg": None, "latest": None},
                "co2": {"min": None, "max": None, "avg": None, "latest": None},
                "smoke_value": {"min": None, "max": None, "avg": None, "latest": None},
                "air_quality": {"min": None, "max": None, "avg": None, "latest": None},
            },
            "occupancy": {"current_count": 5, "total_in": 6, "total_out": 1, "trend": "stable"},
            "active_session": None,
            "recent_events": [],
        },
    },
    "rag_store": {
        # --- get_telemetry: RỖNG — sensor đứt ---
        "get_telemetry": {
            "room_id": ROOM_E502,
            "metric": "temperature",
            "window": "1h",
            "latest": None,
            "avg": None,
            "min": None,
            "max": None,
            "trend": "unknown",
            "samples_count": 0,
            "data_points": [],
            "analysis": "Không có dữ liệu telemetry trong 1h qua. Cảm biến có thể mất kết nối.",
            "sensor_status": "offline",
        },
        # --- get_predictions: Không đủ dữ liệu để dự báo ---
        "get_predictions": {
            "room_id": ROOM_E502,
            "metric": "temperature",
            "horizon": "15m",
            "current_value": None,
            "predicted_value": None,
            "trend": "unknown",
            "confidence": 0.0,
            "model": "EWMA-v2",
            "analysis": "Không đủ dữ liệu lịch sử để dự báo. Cảm biến offline.",
            "error": "insufficient_data",
        },
        # --- get_room_history: Bình thường trước đó ---
        "get_room_history": {
            "room_id": ROOM_E502,
            "hours": 24,
            "transitions": [
                {"timestamp": "2026-09-28T08:00:00+07:00", "mode": "SELF_STUDY", "trigger": "schedule"},
            ],
            "recent_decisions": [],
            "last_sensor_ok": "2026-09-28T13:40:00+07:00",
            "note": "Cảm biến hoạt động bình thường đến 13:40. Mất tín hiệu từ 13:42.",
        },
        # --- search_history: Tiền lệ sensor offline ---
        "search_history": {
            "query": "sensor offline mất kết nối cảm biến nhiệt",
            "results": [
                {
                    "event_type": "temperature_anomaly",
                    "action_taken": "send_alert",
                    "parameters": {"level": "warning", "message": "Cảm biến mất kết nối, cần kiểm tra"},
                    "outcome": "Kỹ thuật viên kiểm tra và khôi phục kết nối sau 20 phút.",
                    "similarity": 0.82,
                },
            ],
        },
        "get_schedule": {
            "room_id": ROOM_E502,
            "date": "2026-09-28",
            "active_session": None,
            "classes_today": [
                {"class_code": "IT102", "start": "07:30", "end": "11:30", "status": "completed"},
            ],
            "note": "Buổi chiều phòng mở tự học, không có lịch cố định.",
        },
        "get_attendance": {
            "room_id": ROOM_E502,
            "class_code": None,
            "enrolled_count": 0,
            "checked_in_count": 0,
            "attendance_rate": 0,
            "status": "no_session",
        },
        "compare_rooms": {
            "metric": "temperature",
            "window": "1h",
            "comparisons": [
                {"room_id": ROOM_E502, "value": None, "status": "sensor_offline"},
                {"room_id": ROOM_A101, "value": 26.5, "status": "normal"},
            ],
            "analysis": "Cảm biến E502 offline — không có dữ liệu so sánh được.",
        },
    },
    "expected_outcome": {
        "skip": False,
        "expected_tool": "send_alert",
        "min_confidence": 0.5,
        "urgency": "medium",
        "reasoning": (
            "Dữ liệu telemetry RỖNG không phải bằng chứng 'an toàn'. "
            "Cảm biến báo 40°C rồi mất tín hiệu — nguy cơ thực hoặc sensor hỏng. "
            "Phải gửi cảnh báo cho kỹ thuật viên kiểm tra, không được skip."
        ),
    },
}


# ===========================================================================
# SCENARIO 8: OCCUPANCY CHANGE — Số người tăng bất thường lúc 23h (nghỉ học)
# Agent phải gọi get_schedule (không có lịch) + get_attendance → đáng nghi
# ===========================================================================
ROOM_B105 = "00000000-0000-0000-0000-000000000105"

SCENARIO_OCCUPANCY_NIGHT = {
    "id": "occupancy_night_anomaly",
    "label": "👥 Occupancy bất thường — 8 người vào phòng lúc 23h",
    "description": (
        "Hệ thống phát hiện occupancy tăng từ 0 lên 8 người tại phòng B105 lúc 23h. "
        "Phòng không có lịch học buổi tối. Đây là hành vi bất thường đáng nghi."
    ),
    "trigger_payload": {
        "event": {
            "event_id": str(uuid4()),
            "event_type": "occupancy_change",
            "room_id": ROOM_B105,
            "timestamp": "2026-09-28T23:05:00+07:00",
            "event_data": {
                "previous_count": 0,
                "current_count": 8,
                "delta": 8,
                "trigger": "count_spike",
            },
        },
        "context": {
            "room": {
                "room_id": ROOM_B105,
                "room_name": "Phòng B105 — Lớp học nhỏ",
                "room_type": "classroom",
                "current_mode": "SAVING",
                "smoke_state": "normal",
            },
            "telemetry_summary": {
                "window_start": "2026-09-28T22:50:00+07:00",
                "window_end": "2026-09-28T23:05:00+07:00",
                "temperature": {"min": 24.0, "max": 25.5, "avg": 24.8, "latest": 25.5},
                "humidity": {"min": 60.0, "max": 65.0, "avg": 62.0, "latest": 63.0},
                "co2": {"min": 400.0, "max": 750.0, "avg": 520.0, "latest": 750.0},
                "smoke_value": {"min": 0.0, "max": 3.0, "avg": 1.0, "latest": 2.0},
                "air_quality": {"min": 85.0, "max": 95.0, "avg": 90.0, "latest": 87.0},
            },
            "occupancy": {"current_count": 8, "total_in": 8, "total_out": 0, "trend": "sudden_increase"},
            "active_session": None,
            "recent_events": [],
        },
    },
    "rag_store": {
        "get_schedule": {
            "room_id": ROOM_B105,
            "date": "2026-09-28",
            "classes_today": [
                {"class_code": "MATH101", "start": "07:30", "end": "09:30", "status": "completed"},
                {"class_code": "ENG201", "start": "13:30", "end": "15:30", "status": "completed"},
            ],
            "active_session": None,
            "note": "Không có lịch học sau 15:30. Phòng không được phân công buổi tối.",
        },
        "get_attendance": {
            "room_id": ROOM_B105,
            "class_code": None,
            "enrolled_count": 0,
            "checked_in_count": 0,
            "attendance_rate": 0,
            "status": "no_active_session",
            "note": "Không có phiên điểm danh nào đang hoạt động lúc 23h.",
        },
        "get_room_history": {
            "room_id": ROOM_B105,
            "hours": 6,
            "transitions": [
                {"timestamp": "2026-09-28T15:30:00+07:00", "mode": "SAVING", "trigger": "class_end"},
            ],
            "recent_decisions": [],
            "note": "Phòng đã ở chế độ SAVING từ 15:30. Không có ai vào ra từ đó đến 22:55.",
        },
        "search_history": {
            "query": "occupancy tăng ban đêm ngoài giờ học",
            "results": [
                {
                    "event_type": "occupancy_change",
                    "action_taken": "send_alert",
                    "parameters": {"level": "warning"},
                    "outcome": "Bảo vệ kiểm tra, phát hiện nhóm sinh viên tự ý ở lại. Đã nhắc nhở.",
                    "similarity": 0.86,
                },
            ],
        },
        "get_telemetry": {
            "room_id": ROOM_B105,
            "metric": "co2",
            "window": "15m",
            "latest": 750.0,
            "avg": 520.0,
            "min": 400.0,
            "max": 750.0,
            "trend": "increasing",
            "samples_count": 6,
            "analysis": "CO2 tăng từ 400 lên 750 trong 15 phút — phù hợp với 8 người vào phòng.",
        },
        "get_predictions": {
            "room_id": ROOM_B105,
            "metric": "temperature",
            "horizon": "15m",
            "current_value": 25.5,
            "predicted_value": 26.0,
            "trend": "stable",
            "confidence": 0.75,
        },
        "compare_rooms": {
            "metric": "occupancy",
            "window": "1h",
            "comparisons": [
                {"room_id": ROOM_B105, "value": 8, "status": "anomaly"},
                {"room_id": ROOM_A101, "value": 0, "status": "normal"},
            ],
            "analysis": "Chỉ B105 có người lúc 23h. Bất thường cục bộ.",
        },
    },
    "expected_outcome": {
        "skip": False,
        "expected_tool": "send_alert",
        "min_confidence": 0.65,
        "urgency": "high",
        "reasoning": (
            "8 người vào phòng lúc 23h, không có lịch học, phòng đang ở SAVING. "
            "CO2 tăng xác nhận có người thực sự trong phòng. "
            "Hành vi bất thường — cần cảnh báo bảo vệ kiểm tra."
        ),
    },
}


# ===========================================================================
# SCENARIO 9: COMBO — Vừa có khói VỪA CÓ nhiệt tăng đồng thời
# Đây là dấu hiệu CHÁY THẬT nghiêm trọng → trigger_buzzer ngay + send_alert
# ===========================================================================
ROOM_F203 = "00000000-0000-0000-0000-000000000203"

SCENARIO_SMOKE_TEMP_COMBO = {
    "id": "smoke_temp_combo_emergency",
    "label": "🚨 COMBO Khẩn Cấp — Vừa có Khói VỪA Nhiệt tăng đồng thời",
    "description": (
        "Phòng F203 phát hiện đồng thời smoke_value=380 (cảnh báo đỏ) "
        "VÀ nhiệt độ tăng từ 26→38°C trong 20 phút. "
        "Đây là dấu hiệu cháy thật nghiêm trọng. Agent phải hành động khẩn cấp."
    ),
    "trigger_payload": {
        "event": {
            "event_id": str(uuid4()),
            "event_type": "smoke_detected",
            "room_id": ROOM_F203,
            "timestamp": "2026-09-28T15:20:00+07:00",
            "event_data": {
                "smoke_value": 380.0,
                "smoke_state": "suspected",
                "mq2_raw": 480,
                "temperature": 38.0,
                "trigger": "smoke_threshold_exceeded",
                "threshold": 300,
            },
        },
        "context": {
            "room": {
                "room_id": ROOM_F203,
                "room_name": "Phòng F203 — Xưởng thực hành điện",
                "room_type": "workshop",
                "current_mode": "LECTURE",
                "smoke_state": "suspected",
            },
            "telemetry_summary": {
                "window_start": "2026-09-28T15:00:00+07:00",
                "window_end": "2026-09-28T15:20:00+07:00",
                "temperature": {"min": 26.0, "max": 38.0, "avg": 31.5, "latest": 38.0},
                "humidity": {"min": 40.0, "max": 55.0, "avg": 47.0, "latest": 43.0},
                "co2": {"min": 700.0, "max": 1600.0, "avg": 1100.0, "latest": 1600.0},
                "smoke_value": {"min": 20.0, "max": 380.0, "avg": 150.0, "latest": 380.0},
                "air_quality": {"min": 20.0, "max": 65.0, "avg": 40.0, "latest": 22.0},
            },
            "occupancy": {"current_count": 18, "total_in": 20, "total_out": 2, "trend": "stable"},
            "active_session": {
                "session_id": str(uuid4()),
                "class_code": "EE401",
                "lecturer_name": "ThS. Trần Thị E",
                "enrolled_count": 20,
                "checked_in_count": 18,
                "started_at": "2026-09-28T14:00:00+07:00",
                "attendance_deadline": "2026-09-28T14:15:00+07:00",
                "is_exam": False,
            },
            "recent_events": [
                {"type": "temperature_anomaly", "time": "2026-09-28T15:10:00+07:00", "extra": {"temperature": 34.5}},
            ],
        },
    },
    "rag_store": {
        "get_telemetry": {
            "room_id": ROOM_F203,
            "metric": "smoke",
            "window": "15m",
            "latest": 380.0,
            "avg": 150.0,
            "min": 20.0,
            "max": 380.0,
            "trend": "sharp_spike",
            "samples_count": 10,
            "data_points": [
                {"time": "15:05", "value": 20},
                {"time": "15:08", "value": 65},
                {"time": "15:11", "value": 140},
                {"time": "15:14", "value": 230},
                {"time": "15:17", "value": 310},
                {"time": "15:20", "value": 380},
            ],
            "analysis": (
                "Khói tăng liên tục 20→380 trong 15 phút ĐỒNG THỜI nhiệt độ "
                "tăng 26→38°C. Hai sensor đều xác nhận sự cố nghiêm trọng."
            ),
        },
        "get_room_history": {
            "room_id": ROOM_F203,
            "hours": 6,
            "smoke_events_past_24h": 0,
            "current_state": "LECTURE",
            "transitions": [
                {"timestamp": "2026-09-28T14:00:00+07:00", "mode": "LECTURE", "trigger": "class_start"},
                {"timestamp": "2026-09-28T15:10:00+07:00", "mode": "SUSPECTED", "trigger": "auto_temp_anomaly"},
            ],
            "recent_decisions": [],
            "note": "Lần đầu phát hiện cả smoke + nhiệt tăng đồng thời. Không có tiền lệ.",
        },
        "get_predictions": {
            "room_id": ROOM_F203,
            "metric": "smoke",
            "horizon": "15m",
            "current_value": 380.0,
            "predicted_value": 650.0,
            "trend": "rising",
            "confidence": 0.95,
            "model": "EWMA-v2",
            "analysis": "CẢNH BÁO: Smoke dự báo vượt 650 trong 15 phút. Nguy cơ cháy thật rất cao.",
        },
        "compare_rooms": {
            "metric": "smoke",
            "window": "15m",
            "comparisons": [
                {"room_id": ROOM_F203, "value": 380.0, "status": "critical"},
                {"room_id": ROOM_B202, "value": 8.0, "status": "normal"},
            ],
            "analysis": "Chỉ F203 có bất thường nghiêm trọng. Sự cố cục bộ, không lan rộng.",
        },
        "search_history": {
            "query": "smoke detected temperature tăng đồng thời cháy",
            "results": [
                {
                    "event_type": "smoke_detected",
                    "action_taken": "trigger_buzzer",
                    "parameters": {"pattern": "continuous"},
                    "outcome": "Sơ tán kịp thời, phát hiện chập điện từ máy biến áp xưởng.",
                    "similarity": 0.91,
                },
            ],
        },
        "get_schedule": {
            "room_id": ROOM_F203,
            "date": "2026-09-28",
            "active_session": {
                "class_code": "EE401",
                "subject": "Thực hành An toàn điện",
                "lecturer": "ThS. Trần Thị E",
                "start": "14:00",
                "end": "18:00",
                "room_mode": "LECTURE",
            },
        },
        "get_attendance": {
            "room_id": ROOM_F203,
            "class_code": "EE401",
            "enrolled_count": 20,
            "checked_in_count": 18,
            "attendance_rate": 0.90,
            "status": "ongoing",
        },
    },
    "expected_outcome": {
        "skip": False,
        "expected_tool": "trigger_buzzer",
        "min_confidence": 0.85,
        "urgency": "critical",
        "reasoning": (
            "Cả smoke VÀ nhiệt đều tăng đồng thời và liên tục. "
            "Dự báo smoke lên 650 trong 15 phút. Có 18 người trong phòng xưởng điện. "
            "KHẨN CẤP: trigger_buzzer + mode EMERGENCY."
        ),
    },
}


# ===========================================================================
# SCENARIO 10: RFID TRONG GIỜ HỌC — Thẻ lạ lúc 9h sáng, có lớp đang diễn ra
# Khác SC5: đây là ban ngày, phòng đang học → nguy cơ thấp hơn, cần đối chiếu
# Expected: skip=True (có thể là sv vào muộn, thẻ cũ) HOẶC send_alert mức thấp
# ===========================================================================
ROOM_A302 = "00000000-0000-0000-0000-000000000302"

SCENARIO_RFID_DURING_CLASS = {
    "id": "rfid_during_class_hours",
    "label": "🎫 RFID lạ trong giờ học — Có lớp đang diễn ra, ít nghi ngờ hơn",
    "description": (
        "Thẻ UID lạ quẹt vào phòng A302 lúc 9:15 sáng, đang có lớp học CS201. "
        "Phòng có 30 sinh viên đã vào trong 30. Thẻ có thể là của sinh viên đến muộn "
        "hoặc thẻ mới chưa cập nhật hệ thống. Nguy cơ an ninh thấp hơn nhiều so với ban đêm."
    ),
    "trigger_payload": {
        "event": {
            "event_id": str(uuid4()),
            "event_type": "rfid_unknown",
            "room_id": ROOM_A302,
            "timestamp": "2026-09-28T09:15:00+07:00",
            "event_data": {
                "card_uid": "A3:F1:88:2B",
                "reader_id": "door-main",
                "scan_result": "unknown",
            },
        },
        "context": {
            "room": {
                "room_id": ROOM_A302,
                "room_name": "Phòng A302 — Lớp học",
                "room_type": "classroom",
                "current_mode": "LECTURE",
                "smoke_state": "normal",
            },
            "telemetry_summary": {
                "window_start": "2026-09-28T09:00:00+07:00",
                "window_end": "2026-09-28T09:15:00+07:00",
                "temperature": {"min": 24.0, "max": 26.0, "avg": 25.0, "latest": 25.5},
                "humidity": {"min": 55.0, "max": 62.0, "avg": 58.0, "latest": 59.0},
                "co2": {"min": 500.0, "max": 850.0, "avg": 680.0, "latest": 850.0},
                "smoke_value": {"min": 0.0, "max": 5.0, "avg": 2.0, "latest": 3.0},
                "air_quality": {"min": 75.0, "max": 90.0, "avg": 83.0, "latest": 80.0},
            },
            "occupancy": {"current_count": 30, "total_in": 31, "total_out": 1, "trend": "stable"},
            "active_session": {
                "session_id": str(uuid4()),
                "class_code": "CS201",
                "lecturer_name": "TS. Phạm Văn F",
                "enrolled_count": 35,
                "checked_in_count": 30,
                "started_at": "2026-09-28T08:00:00+07:00",
                "attendance_deadline": "2026-09-28T08:15:00+07:00",
                "is_exam": False,
            },
            "recent_events": [],
        },
    },
    "rag_store": {
        "get_schedule": {
            "room_id": ROOM_A302,
            "date": "2026-09-28",
            "active_session": {
                "class_code": "CS201",
                "subject": "Lập trình hướng đối tượng",
                "lecturer": "TS. Phạm Văn F",
                "start": "08:00",
                "end": "10:00",
                "room_mode": "LECTURE",
            },
        },
        "get_room_history": {
            "room_id": ROOM_A302,
            "hours": 24,
            "transitions": [
                {"timestamp": "2026-09-28T08:00:00+07:00", "mode": "LECTURE", "trigger": "class_start"},
            ],
            "recent_decisions": [],
            "note": "Không có sự kiện rfid_unknown nào trong 24h qua. Lần đầu.",
        },
        "get_attendance": {
            "room_id": ROOM_A302,
            "class_code": "CS201",
            "enrolled_count": 35,
            "checked_in_count": 30,
            "attendance_rate": 0.857,
            "status": "ongoing",
            "note": "Còn 5 sinh viên chưa điểm danh — có thể đây là 1 trong số họ.",
        },
        "search_history": {
            "query": "rfid_unknown trong giờ học sinh viên muộn",
            "results": [
                {
                    "event_type": "rfid_unknown",
                    "action_taken": "skip",
                    "parameters": {},
                    "outcome": "Sinh viên vào muộn với thẻ mới chưa đồng bộ. Không có vấn đề.",
                    "similarity": 0.79,
                },
            ],
        },
        "get_telemetry": {
            "room_id": ROOM_A302,
            "metric": "temperature",
            "window": "1h",
            "latest": 25.5,
            "avg": 25.0,
            "min": 24.0,
            "max": 26.0,
            "trend": "stable",
            "samples_count": 12,
        },
        "get_predictions": {
            "room_id": ROOM_A302,
            "metric": "temperature",
            "horizon": "15m",
            "current_value": 25.5,
            "predicted_value": 25.8,
            "trend": "stable",
            "confidence": 0.90,
        },
        "compare_rooms": {
            "metric": "temperature",
            "window": "1h",
            "comparisons": [
                {"room_id": ROOM_A302, "value": 25.5, "status": "normal"},
                {"room_id": ROOM_A101, "value": 26.0, "status": "normal"},
            ],
        },
    },
    "expected_outcome": {
        "skip": True,
        "expected_tool": None,
        "max_confidence": 0.5,
        "reasoning": (
            "Thẻ lạ trong giờ học, có 5 sv chưa điểm danh trong danh sách lớp. "
            "Tiền lệ tương tự đã skip (sv vào muộn). Nguy cơ thấp → skip hợp lý."
        ),
    },
}


# ===========================================================================
# SCENARIO 11: CO2 CAO — CO2 vượt 2000ppm trong phòng học kín
# Không phải cháy, là vấn đề không khí → set_fan thông gió
# ===========================================================================
ROOM_G101 = "00000000-0000-0000-0000-000000000601"

SCENARIO_CO2_HIGH = {
    "id": "co2_high_ventilation_needed",
    "label": "💨 CO2 cao — 2100ppm, cần thông gió gấp",
    "description": (
        "Phòng G101 có CO2 tăng lên 2100ppm (ngưỡng nguy hiểm 1500ppm). "
        "Nhiệt độ bình thường, không có khói. Nguyên nhân: phòng kín với 42 người, "
        "điều hòa tắt lọc không khí. Agent phải bật quạt thông gió."
    ),
    "trigger_payload": {
        "event": {
            "event_id": str(uuid4()),
            "event_type": "temperature_anomaly",
            "room_id": ROOM_G101,
            "timestamp": "2026-09-28T10:30:00+07:00",
            "event_data": {
                "temperature": 27.5,
                "humidity": 70.0,
                "co2": 2100,
                "smoke_value": 5.0,
                "trigger": "co2_threshold_exceeded",
                "threshold": 1500,
            },
        },
        "context": {
            "room": {
                "room_id": ROOM_G101,
                "room_name": "Phòng G101 — Hội trường nhỏ",
                "room_type": "lecture_hall",
                "current_mode": "LECTURE",
                "smoke_state": "normal",
            },
            "telemetry_summary": {
                "window_start": "2026-09-28T10:00:00+07:00",
                "window_end": "2026-09-28T10:30:00+07:00",
                "temperature": {"min": 26.5, "max": 28.0, "avg": 27.2, "latest": 27.5},
                "humidity": {"min": 65.0, "max": 72.0, "avg": 68.0, "latest": 70.0},
                "co2": {"min": 900.0, "max": 2100.0, "avg": 1500.0, "latest": 2100.0},
                "smoke_value": {"min": 2.0, "max": 8.0, "avg": 4.0, "latest": 5.0},
                "air_quality": {"min": 25.0, "max": 55.0, "avg": 38.0, "latest": 28.0},
            },
            "occupancy": {"current_count": 42, "total_in": 44, "total_out": 2, "trend": "stable"},
            "active_session": {
                "session_id": str(uuid4()),
                "class_code": "MBA501",
                "lecturer_name": "GS. Lê Văn G",
                "enrolled_count": 45,
                "checked_in_count": 42,
                "started_at": "2026-09-28T08:30:00+07:00",
                "attendance_deadline": "2026-09-28T08:45:00+07:00",
                "is_exam": False,
            },
            "recent_events": [],
        },
    },
    "rag_store": {
        "get_telemetry": {
            "room_id": ROOM_G101,
            "metric": "co2",
            "window": "1h",
            "latest": 2100.0,
            "avg": 1500.0,
            "min": 900.0,
            "max": 2100.0,
            "trend": "increasing",
            "samples_count": 24,
            "data_points": [
                {"time": "09:30", "value": 900},
                {"time": "09:45", "value": 1100},
                {"time": "10:00", "value": 1350},
                {"time": "10:15", "value": 1700},
                {"time": "10:30", "value": 2100},
            ],
            "analysis": (
                "CO2 tăng đều 900→2100ppm trong 1 giờ. Vượt ngưỡng nguy hiểm sức khỏe (1500ppm). "
                "Nhiệt độ ổn định — đây là vấn đề thông khí, không phải cháy."
            ),
        },
        "get_predictions": {
            "room_id": ROOM_G101,
            "metric": "co2",
            "horizon": "15m",
            "current_value": 2100.0,
            "predicted_value": 2400.0,
            "trend": "rising",
            "confidence": 0.88,
            "model": "EWMA-v2",
            "analysis": "CO2 dự báo tăng lên 2400ppm nếu không thông gió — mức gây choáng ngất.",
        },
        "compare_rooms": {
            "metric": "co2",
            "window": "1h",
            "comparisons": [
                {"room_id": ROOM_G101, "value": 2100.0, "status": "critical"},
                {"room_id": ROOM_A101, "value": 850.0, "status": "normal"},
            ],
            "analysis": "Chỉ G101 có CO2 nguy hiểm. Vấn đề thông khí cục bộ.",
        },
        "get_schedule": {
            "room_id": ROOM_G101,
            "date": "2026-09-28",
            "active_session": {
                "class_code": "MBA501",
                "subject": "Quản trị chiến lược",
                "lecturer": "GS. Lê Văn G",
                "start": "08:30",
                "end": "12:00",
                "room_mode": "LECTURE",
            },
        },
        "get_room_history": {
            "room_id": ROOM_G101,
            "hours": 2,
            "transitions": [
                {"timestamp": "2026-09-28T08:30:00+07:00", "mode": "LECTURE", "trigger": "class_start"},
            ],
            "recent_decisions": [],
            "note": "Không có hành động thông gió nào được thực hiện trong buổi học.",
        },
        "search_history": {
            "query": "co2 cao thông gió phòng học",
            "results": [
                {
                    "event_type": "temperature_anomaly",
                    "action_taken": "set_fan",
                    "parameters": {"state": "on"},
                    "outcome": "CO2 giảm về 800ppm sau 20 phút bật quạt.",
                    "similarity": 0.83,
                },
            ],
        },
        "get_attendance": {
            "room_id": ROOM_G101,
            "class_code": "MBA501",
            "enrolled_count": 45,
            "checked_in_count": 42,
            "attendance_rate": 0.93,
            "status": "ongoing",
        },
    },
    "expected_outcome": {
        "skip": False,
        "expected_tool": "set_fan",
        "min_confidence": 0.72,
        "urgency": "high",
        "reasoning": (
            "CO2 2100ppm vượt ngưỡng sức khỏe, tăng liên tục và dự báo lên 2400ppm. "
            "Có 42 người trong phòng. Đây là vấn đề thông khí, set_fan là giải pháp đúng."
        ),
    },
}


# ===========================================================================
# SCENARIO 12: MANUAL TRIGGER TRONG GIỜ THI — Lệnh khóa cửa trong EXAM
# FSM conflict: set_door không được phép trong EXAM → skip với giải thích rõ
# ===========================================================================
ROOM_H201 = "00000000-0000-0000-0000-000000000701"

SCENARIO_MANUAL_EXAM_CONFLICT = {
    "id": "manual_door_lock_exam_conflict",
    "label": "🚫 Manual Trigger — Lệnh khóa cửa trong giờ thi bị từ chối",
    "description": (
        "Giám thị gửi lệnh thủ công set_door (khóa cửa) cho phòng H201 "
        "đang tổ chức thi. Tuy nhiên trong EXAM mode, set_door bị khóa bởi "
        "permission matrix (an toàn thoát hiểm). Agent phải từ chối và giải thích."
    ),
    "trigger_payload": {
        "event": {
            "event_id": str(uuid4()),
            "event_type": "manual_trigger",
            "room_id": ROOM_H201,
            "timestamp": "2026-09-28T09:00:00+07:00",
            "event_data": {
                "requested_tool": "set_door",
                "requested_params": {"state": "locked"},
                "requested_by": "staff_001",
                "reason": "Giám thị yêu cầu khóa cửa để tránh thí sinh ra vào",
            },
        },
        "context": {
            "room": {
                "room_id": ROOM_H201,
                "room_name": "Phòng H201 — Phòng thi lớn",
                "room_type": "lecture_hall",
                "current_mode": "EXAM",
                "smoke_state": "normal",
            },
            "telemetry_summary": {
                "window_start": "2026-09-28T08:45:00+07:00",
                "window_end": "2026-09-28T09:00:00+07:00",
                "temperature": {"min": 24.0, "max": 25.5, "avg": 24.8, "latest": 25.0},
                "humidity": {"min": 55.0, "max": 60.0, "avg": 57.0, "latest": 58.0},
                "co2": {"min": 400.0, "max": 700.0, "avg": 550.0, "latest": 700.0},
                "smoke_value": {"min": 0.0, "max": 3.0, "avg": 1.0, "latest": 2.0},
                "air_quality": {"min": 85.0, "max": 95.0, "avg": 90.0, "latest": 88.0},
            },
            "occupancy": {"current_count": 55, "total_in": 56, "total_out": 1, "trend": "stable"},
            "active_session": {
                "session_id": str(uuid4()),
                "class_code": "FINAL_CS_K22",
                "lecturer_name": "Hội đồng thi",
                "enrolled_count": 60,
                "checked_in_count": 55,
                "started_at": "2026-09-28T08:00:00+07:00",
                "attendance_deadline": "2026-09-28T08:20:00+07:00",
                "is_exam": True,
            },
            "recent_events": [],
        },
    },
    "rag_store": {
        "get_room_history": {
            "room_id": ROOM_H201,
            "hours": 1,
            "transitions": [
                {"timestamp": "2026-09-28T07:50:00+07:00", "mode": "EXAM", "trigger": "exam_start"},
            ],
            "recent_decisions": [],
            "note": "Phòng đang thi, mọi thứ bình thường. Không có sự kiện nào trước đó.",
        },
        "get_schedule": {
            "room_id": ROOM_H201,
            "date": "2026-09-28",
            "active_session": {
                "class_code": "FINAL_CS_K22",
                "subject": "Thi cuối kỳ — Khoa học máy tính K22",
                "start": "08:00",
                "end": "10:30",
                "room_mode": "EXAM",
                "is_exam": True,
                "exam_rules": "Không khóa cửa cơ học trong giờ thi (quy định PCCC).",
            },
        },
        "get_telemetry": {
            "room_id": ROOM_H201,
            "metric": "temperature",
            "window": "1h",
            "latest": 25.0,
            "avg": 24.8,
            "min": 24.0,
            "max": 25.5,
            "trend": "stable",
            "samples_count": 12,
        },
        "get_predictions": {
            "room_id": ROOM_H201,
            "metric": "temperature",
            "horizon": "15m",
            "current_value": 25.0,
            "predicted_value": 25.2,
            "trend": "stable",
            "confidence": 0.92,
        },
        "search_history": {
            "query": "manual set_door exam mode khóa cửa thi",
            "results": [
                {
                    "event_type": "manual_trigger",
                    "action_taken": "skip",
                    "parameters": {},
                    "outcome": "Từ chối set_door trong EXAM — vi phạm quy định an toàn thoát hiểm.",
                    "similarity": 0.91,
                },
            ],
        },
        "get_attendance": {
            "room_id": ROOM_H201,
            "class_code": "FINAL_CS_K22",
            "enrolled_count": 60,
            "checked_in_count": 55,
            "attendance_rate": 0.917,
            "status": "exam_in_progress",
        },
        "compare_rooms": {
            "metric": "temperature",
            "window": "1h",
            "comparisons": [
                {"room_id": ROOM_H201, "value": 25.0, "status": "normal"},
            ],
        },
    },
    "expected_outcome": {
        "skip": True,
        "expected_tool": None,
        "reasoning": (
            "set_door (locked) không được phép trong EXAM mode — vi phạm quy định PCCC "
            "và permission matrix. Không có emergency. Agent phải từ chối và giải thích rõ lý do."
        ),
    },
}


# ===========================================================================
# SCENARIO 13: RFID LẶP LẠI — Cùng thẻ lạ quẹt 3 lần trong 2 giờ
# Lịch sử có tiền lệ: thẻ này đã từng bị từ chối → tăng nguy cơ → send_alert
# ===========================================================================
ROOM_A204_2 = ROOM_A204  # Tái dùng phòng A204

SCENARIO_RFID_REPEATED = {
    "id": "rfid_repeated_same_card",
    "label": "🔁 RFID lạ lặp lại — Cùng thẻ quẹt 3 lần, đã từng bị từ chối",
    "description": (
        "Thẻ UID B7:E3:22:1A (đã bị từ chối tối qua) lại tiếp tục quẹt "
        "3 lần trong vòng 2 giờ tại phòng A204. Hành vi lặp lại + tiền lệ xấu "
        "→ nguy cơ cao hơn, cần cảnh báo gấp."
    ),
    "trigger_payload": {
        "event": {
            "event_id": str(uuid4()),
            "event_type": "rfid_unknown",
            "room_id": ROOM_A204,
            "timestamp": "2026-09-28T14:30:00+07:00",
            "event_data": {
                "card_uid": "B7:E3:22:1A",
                "reader_id": "door-main",
                "scan_result": "unknown",
                "attempt_count_today": 3,
            },
        },
        "context": {
            "room": {
                "room_id": ROOM_A204,
                "room_name": "Phòng A204",
                "room_type": "lecture_hall",
                "current_mode": "SAVING",
                "smoke_state": "normal",
            },
            "telemetry_summary": {
                "window_start": "2026-09-28T14:15:00+07:00",
                "window_end": "2026-09-28T14:30:00+07:00",
                "temperature": {"min": 24.0, "max": 25.5, "avg": 24.8, "latest": 25.0},
                "humidity": {"min": 55.0, "max": 62.0, "avg": 58.0, "latest": 59.0},
                "co2": {"min": 350.0, "max": 450.0, "avg": 400.0, "latest": 420.0},
                "smoke_value": {"min": 0.0, "max": 2.0, "avg": 0.5, "latest": 1.0},
                "air_quality": {"min": 88.0, "max": 95.0, "avg": 92.0, "latest": 91.0},
            },
            "occupancy": {"current_count": 0, "total_in": 0, "total_out": 0, "trend": "empty"},
            "active_session": None,
            "recent_events": [
                {"type": "rfid_unknown", "time": "2026-09-28T12:15:00+07:00",
                 "extra": {"card_uid": "B7:E3:22:1A"}},
                {"type": "rfid_unknown", "time": "2026-09-28T13:45:00+07:00",
                 "extra": {"card_uid": "B7:E3:22:1A"}},
            ],
        },
    },
    "rag_store": {
        "get_schedule": {
            "room_id": ROOM_A204,
            "date": "2026-09-28",
            "classes_today": [
                {"class_code": "CS101", "start": "07:30", "end": "11:30", "status": "completed"},
                {"class_code": "MATH201", "start": "13:30", "end": "14:00", "status": "completed"},
            ],
            "active_session": None,
            "note": "Hết lịch từ 14:00. Phòng trống trong giờ xảy ra sự kiện.",
        },
        "get_room_history": {
            "room_id": ROOM_A204,
            "hours": 24,
            "current_state": "SAVING",
            "transitions": [
                {"timestamp": "2026-09-28T14:00:00+07:00", "mode": "SAVING", "trigger": "class_end"},
            ],
            "rfid_events": [
                {"card_uid": "B7:E3:22:1A", "time": "2026-09-27T22:00:00+07:00",
                 "decision": "send_alert", "note": "Thẻ lạ ban đêm, đã cảnh báo bảo vệ"},
                {"card_uid": "B7:E3:22:1A", "time": "2026-09-28T12:15:00+07:00",
                 "decision": "pending"},
                {"card_uid": "B7:E3:22:1A", "time": "2026-09-28T13:45:00+07:00",
                 "decision": "pending"},
            ],
            "note": "Thẻ B7:E3:22:1A đã quẹt 3 lần hôm nay + 1 lần tối qua. Hành vi lặp lại đáng nghi.",
        },
        "get_attendance": {
            "room_id": ROOM_A204,
            "class_code": None,
            "enrolled_count": 0,
            "checked_in_count": 0,
            "attendance_rate": 0,
            "status": "no_active_session",
        },
        "search_history": {
            "query": "rfid_unknown thẻ lạ lặp lại nhiều lần",
            "results": [
                {
                    "event_type": "rfid_unknown",
                    "action_taken": "send_alert",
                    "parameters": {"level": "critical"},
                    "outcome": "Bảo vệ phát hiện người lạ cố ý vào phòng thiết bị. Đã xử lý.",
                    "similarity": 0.93,
                },
            ],
        },
        "get_telemetry": {
            "room_id": ROOM_A204,
            "metric": "temperature",
            "window": "1h",
            "latest": 25.0,
            "avg": 24.8,
            "min": 24.0,
            "max": 25.5,
            "trend": "stable",
            "samples_count": 12,
        },
        "get_predictions": {
            "room_id": ROOM_A204,
            "metric": "temperature",
            "horizon": "15m",
            "current_value": 25.0,
            "predicted_value": 24.8,
            "trend": "stable",
            "confidence": 0.93,
        },
        "compare_rooms": {
            "metric": "temperature",
            "window": "1h",
            "comparisons": [
                {"room_id": ROOM_A204, "value": 25.0, "status": "normal"},
            ],
        },
    },
    "expected_outcome": {
        "skip": False,
        "expected_tool": "send_alert",
        "min_confidence": 0.75,
        "urgency": "high",
        "reasoning": (
            "Cùng 1 thẻ UID đã quẹt 3 lần hôm nay + 1 lần tối qua (đã từng bị cảnh báo). "
            "Phòng trống, hết giờ học. Hành vi lặp lại có chủ đích → nguy cơ cao."
        ),
    },
}


# ===========================================================================
# SCENARIO 14: MULTI-ROOM TEMP — Nhiều phòng cùng tăng nhiệt (vấn đề hệ thống)
# compare_rooms cho thấy 3/3 phòng đều nóng → hỏng hệ thống HVAC trung tâm
# Agent phải nhận ra đây là vấn đề HỆ THỐNG, không phải sự cố cục bộ
# ===========================================================================
ROOM_BLOCK_A = "00000000-0000-0000-0000-000000000901"

SCENARIO_SYSTEM_TEMP_WIDE = {
    "id": "temp_system_wide_hvac_failure",
    "label": "🌡️ Hệ thống — Nhiều phòng cùng tăng nhiệt (HVAC trung tâm hỏng)",
    "description": (
        "Phòng A-Block báo nhiệt 36°C. compare_rooms cho thấy TẤT CẢ 4 phòng "
        "cùng tòa đều tăng nhiệt đồng thời (34-36°C). "
        "Đây là dấu hiệu hỏng HVAC trung tâm, không phải sự cố cục bộ. "
        "Hành động 1 phòng không hiệu quả — Agent cần send_alert cho ban quản lý."
    ),
    "trigger_payload": {
        "event": {
            "event_id": str(uuid4()),
            "event_type": "temperature_anomaly",
            "room_id": ROOM_BLOCK_A,
            "timestamp": "2026-09-28T11:00:00+07:00",
            "event_data": {
                "temperature": 36.0,
                "humidity": 62.0,
                "co2": 950,
                "smoke_value": 3.0,
                "trigger": "threshold_exceeded",
                "threshold": 34.0,
            },
        },
        "context": {
            "room": {
                "room_id": ROOM_BLOCK_A,
                "room_name": "Phòng A101-Block A (tầng 1)",
                "room_type": "lecture_hall",
                "current_mode": "LECTURE",
                "smoke_state": "normal",
            },
            "telemetry_summary": {
                "window_start": "2026-09-28T10:30:00+07:00",
                "window_end": "2026-09-28T11:00:00+07:00",
                "temperature": {"min": 30.0, "max": 36.0, "avg": 33.2, "latest": 36.0},
                "humidity": {"min": 58.0, "max": 65.0, "avg": 61.0, "latest": 62.0},
                "co2": {"min": 700.0, "max": 1000.0, "avg": 850.0, "latest": 950.0},
                "smoke_value": {"min": 0.0, "max": 5.0, "avg": 2.0, "latest": 3.0},
                "air_quality": {"min": 55.0, "max": 75.0, "avg": 65.0, "latest": 58.0},
            },
            "occupancy": {"current_count": 35, "total_in": 36, "total_out": 1, "trend": "stable"},
            "active_session": {
                "session_id": str(uuid4()),
                "class_code": "MGT201",
                "lecturer_name": "TS. Bùi Văn H",
                "enrolled_count": 38,
                "checked_in_count": 35,
                "started_at": "2026-09-28T09:30:00+07:00",
                "attendance_deadline": "2026-09-28T09:45:00+07:00",
                "is_exam": False,
            },
            "recent_events": [
                {
                    "event_type": "temperature_anomaly",
                    "room_id": "00000000-0000-0000-0000-000000000902",
                    "timestamp": "2026-09-28T10:45:00+07:00"
                },
                {
                    "event_type": "temperature_anomaly",
                    "room_id": "00000000-0000-0000-0000-000000000903",
                    "timestamp": "2026-09-28T10:50:00+07:00"
                }
            ],
        },
    },
    "rag_store": {
        "get_telemetry": {
            "room_id": ROOM_BLOCK_A,
            "metric": "temperature",
            "window": "1h",
            "latest": 36.0,
            "avg": 33.2,
            "min": 30.0,
            "max": 36.0,
            "trend": "increasing",
            "samples_count": 18,
            "analysis": "Nhiệt độ tăng từ 30→36°C trong 30 phút. Tốc độ tăng tương đối đều.",
        },
        "get_predictions": {
            "room_id": ROOM_BLOCK_A,
            "metric": "temperature",
            "horizon": "15m",
            "current_value": 36.0,
            "predicted_value": 37.5,
            "trend": "rising",
            "confidence": 0.83,
            "model": "EWMA-v2",
            "analysis": "Dự báo tăng lên 37.5°C. Tuy nhiên nếu nguyên nhân là HVAC thì set_fan 1 phòng không giải quyết.",
        },
        # --- KEY DATA: compare_rooms cho thấy SỰ CỐ HỆ THỐNG ---
        "compare_rooms": {
            "metric": "temperature",
            "window": "1h",
            "comparisons": [
                {"room_id": ROOM_BLOCK_A, "value": 36.0, "status": "anomaly"},
                {"room_id": "00000000-0000-0000-0000-000000000902", "value": 34.5, "status": "anomaly"},
                {"room_id": "00000000-0000-0000-0000-000000000903", "value": 35.2, "status": "anomaly"},
                {"room_id": "00000000-0000-0000-0000-000000000904", "value": 34.0, "status": "warning"},
            ],
            "analysis": (
                "TẤT CẢ 4 phòng trong Block A đều tăng nhiệt đồng loạt (34-36°C). "
                "Đây KHÔNG phải sự cố cục bộ — khả năng cao là HVAC trung tâm Block A bị hỏng."
            ),
        },
        "get_schedule": {
            "room_id": ROOM_BLOCK_A,
            "date": "2026-09-28",
            "active_session": {
                "class_code": "MGT201",
                "subject": "Quản trị học",
                "lecturer": "TS. Bùi Văn H",
                "start": "09:30",
                "end": "11:30",
                "room_mode": "LECTURE",
            },
        },
        "get_room_history": {
            "room_id": ROOM_BLOCK_A,
            "hours": 2,
            "transitions": [
                {"timestamp": "2026-09-28T09:30:00+07:00", "mode": "LECTURE", "trigger": "class_start"},
            ],
            "recent_decisions": [],
            "note": "Không có vấn đề gì bất thường 2 giờ qua. Hệ thống HVAC có lịch bảo trì ngày 30/9.",
        },
        "search_history": {
            "query": "temperature tăng nhiều phòng hệ thống HVAC",
            "results": [
                {
                    "event_type": "temperature_anomaly",
                    "action_taken": "send_alert",
                    "parameters": {"level": "critical", "message": "HVAC Block A nghi bị hỏng"},
                    "outcome": "Kỹ thuật xác nhận máy nén HVAC tầng 1 hỏng. Sửa trong 2h.",
                    "similarity": 0.87,
                },
            ],
        },
        "get_attendance": {
            "room_id": ROOM_BLOCK_A,
            "class_code": "MGT201",
            "enrolled_count": 38,
            "checked_in_count": 35,
            "attendance_rate": 0.92,
            "status": "ongoing",
        },
    },
    "expected_outcome": {
        "skip": False,
        "expected_tool": "send_alert",
        "min_confidence": 0.72,
        "urgency": "high",
        "reasoning": (
            "compare_rooms xác nhận 4/4 phòng Block A đều bất thường đồng thời — "
            "dấu hiệu HVAC trung tâm hỏng, không phải sự cố cục bộ. "
            "set_fan 1 phòng không đủ. Cần send_alert cho ban quản lý/kỹ thuật."
        ),
    },
}


# ===========================================================================
# SCENARIO 15: NHIỆT PHÒNG TRỐNG — Nhiệt tăng 38°C nhưng phòng không có người
# Nguy cơ hỏa hoạn thật nhưng không có người → hành động khác (set_mode EMERGENCY)
# ===========================================================================
ROOM_STORAGE = "00000000-0000-0000-0000-000000001001"

SCENARIO_TEMP_EMPTY_ROOM = {
    "id": "temp_high_empty_room",
    "label": "🌡️🏚️ Nhiệt cao phòng trống — 38°C, không có người, có thể cháy thiết bị",
    "description": (
        "Phòng kho thiết bị IT (không có người) bất ngờ báo nhiệt 38°C tăng liên tục. "
        "Không có lịch học. Occupancy = 0. Có thể do thiết bị quá nhiệt (server/UPS). "
        "Agent cần hành động dù không có người: send_alert kỹ thuật + set_mode SUSPECTED."
    ),
    "trigger_payload": {
        "event": {
            "event_id": str(uuid4()),
            "event_type": "temperature_anomaly",
            "room_id": ROOM_STORAGE,
            "timestamp": "2026-09-28T03:00:00+07:00",
            "event_data": {
                "temperature": 38.5,
                "humidity": 35.0,
                "co2": 500,
                "smoke_value": 45.0,
                "trigger": "threshold_exceeded",
                "threshold": 34.0,
            },
        },
        "context": {
            "room": {
                "room_id": ROOM_STORAGE,
                "room_name": "Phòng Kho IT — Tầng hầm B1",
                "room_type": "storage",
                "current_mode": "SAVING",
                "smoke_state": "normal",
            },
            "telemetry_summary": {
                "window_start": "2026-09-28T02:30:00+07:00",
                "window_end": "2026-09-28T03:00:00+07:00",
                "temperature": {"min": 26.0, "max": 38.5, "avg": 31.5, "latest": 38.5},
                "humidity": {"min": 30.0, "max": 40.0, "avg": 35.0, "latest": 35.0},
                "co2": {"min": 380.0, "max": 520.0, "avg": 440.0, "latest": 500.0},
                "smoke_value": {"min": 5.0, "max": 45.0, "avg": 20.0, "latest": 45.0},
                "air_quality": {"min": 50.0, "max": 75.0, "avg": 62.0, "latest": 55.0},
            },
            "occupancy": {"current_count": 0, "total_in": 0, "total_out": 0, "trend": "empty"},
            "active_session": None,
            "recent_events": [],
        },
    },
    "rag_store": {
        "get_telemetry": {
            "room_id": ROOM_STORAGE,
            "metric": "temperature",
            "window": "1h",
            "latest": 38.5,
            "avg": 31.5,
            "min": 26.0,
            "max": 38.5,
            "trend": "sharp_increase",
            "samples_count": 12,
            "data_points": [
                {"time": "02:00", "value": 26.0},
                {"time": "02:15", "value": 28.5},
                {"time": "02:30", "value": 31.0},
                {"time": "02:45", "value": 35.0},
                {"time": "03:00", "value": 38.5},
            ],
            "analysis": (
                "Nhiệt tăng +12.5°C trong 1 giờ (26→38.5°C) lúc 3h sáng — phòng kho không có người. "
                "Smoke cũng bắt đầu tăng (5→45). Có thể thiết bị điện quá nhiệt."
            ),
        },
        "get_predictions": {
            "room_id": ROOM_STORAGE,
            "metric": "temperature",
            "horizon": "15m",
            "current_value": 38.5,
            "predicted_value": 41.0,
            "trend": "rising",
            "confidence": 0.91,
            "model": "EWMA-v2",
            "analysis": "Dự báo nhiệt tiếp tục tăng lên 41°C — nguy cơ cháy thiết bị rất cao.",
        },
        "compare_rooms": {
            "metric": "temperature",
            "window": "1h",
            "comparisons": [
                {"room_id": ROOM_STORAGE, "value": 38.5, "status": "critical"},
                {"room_id": ROOM_A101, "value": 24.5, "status": "normal"},
            ],
            "analysis": "Chỉ kho IT bất thường lúc 3h sáng. Sự cố cục bộ, không phải thời tiết.",
        },
        "get_schedule": {
            "room_id": ROOM_STORAGE,
            "date": "2026-09-28",
            "classes_today": [],
            "active_session": None,
            "note": "Phòng kho không có lịch. Chỉ nhân viên IT có quyền vào.",
        },
        "get_room_history": {
            "room_id": ROOM_STORAGE,
            "hours": 24,
            "transitions": [
                {"timestamp": "2026-09-27T18:00:00+07:00", "mode": "SAVING", "trigger": "auto_night_mode"},
            ],
            "recent_decisions": [],
            "note": "Phòng kho bình thường từ 18h hôm qua. Không có sự kiện bất thường.",
        },
        "search_history": {
            "query": "temperature cao phòng kho thiết bị server quá nhiệt",
            "results": [
                {
                    "event_type": "temperature_anomaly",
                    "action_taken": "send_alert",
                    "parameters": {"level": "critical"},
                    "outcome": "Phát hiện UPS quá nhiệt lúc 2h sáng. Xử lý kịp thời tránh cháy.",
                    "similarity": 0.89,
                },
            ],
        },
        "get_attendance": {
            "room_id": ROOM_STORAGE,
            "class_code": None,
            "enrolled_count": 0,
            "checked_in_count": 0,
            "attendance_rate": 0,
            "status": "no_session",
        },
    },
    "expected_outcome": {
        "skip": False,
        "expected_tool": "send_alert",
        "min_confidence": 0.78,
        "urgency": "critical",
        "reasoning": (
            "Nhiệt tăng 12.5°C/giờ lúc 3h sáng trong phòng kho thiết bị điện. "
            "Smoke cũng bắt đầu tăng. Dù không có người nhưng nguy cơ cháy thiết bị IT cao. "
            "Phải gửi cảnh báo khẩn cấp cho kỹ thuật/bảo vệ trực đêm."
        ),
    },
}


# ===========================================================================
# REGISTRY — Truy cập tất cả scenarios
# ===========================================================================
SCENARIOS: dict[str, dict] = {
    SCENARIO_FIRE_REAL["id"]: SCENARIO_FIRE_REAL,
    SCENARIO_TEMP_NOISE["id"]: SCENARIO_TEMP_NOISE,
    SCENARIO_SMOKE_REAL["id"]: SCENARIO_SMOKE_REAL,
    SCENARIO_SMOKE_NOISE["id"]: SCENARIO_SMOKE_NOISE,
    SCENARIO_RFID_NIGHT["id"]: SCENARIO_RFID_NIGHT,
    # --- 10 kịch bản mới ---
    SCENARIO_EXAM_TEMP_FSM["id"]: SCENARIO_EXAM_TEMP_FSM,
    SCENARIO_SENSOR_DEAD["id"]: SCENARIO_SENSOR_DEAD,
    SCENARIO_OCCUPANCY_NIGHT["id"]: SCENARIO_OCCUPANCY_NIGHT,
    SCENARIO_SMOKE_TEMP_COMBO["id"]: SCENARIO_SMOKE_TEMP_COMBO,
    SCENARIO_RFID_DURING_CLASS["id"]: SCENARIO_RFID_DURING_CLASS,
    SCENARIO_CO2_HIGH["id"]: SCENARIO_CO2_HIGH,
    SCENARIO_MANUAL_EXAM_CONFLICT["id"]: SCENARIO_MANUAL_EXAM_CONFLICT,
    SCENARIO_RFID_REPEATED["id"]: SCENARIO_RFID_REPEATED,
    SCENARIO_SYSTEM_TEMP_WIDE["id"]: SCENARIO_SYSTEM_TEMP_WIDE,
    SCENARIO_TEMP_EMPTY_ROOM["id"]: SCENARIO_TEMP_EMPTY_ROOM,
}


def get_rag_response(
    scenario: dict,
    tool_name: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Lấy mock response cho 1 RAG tool từ scenario's rag_store.

    Trả về data tương ứng nếu có, hoặc fallback dict rỗng với warning.
    """
    store = scenario.get("rag_store", {})
    if tool_name in store:
        return store[tool_name]
    return {"warning": f"Tool '{tool_name}' không có dữ liệu mock trong scenario '{scenario.get('id')}'"}


def list_scenario_ids() -> list[str]:
    """Liệt kê tất cả scenario IDs."""
    return list(SCENARIOS.keys())


def get_scenario_summary() -> str:
    """In tóm tắt tất cả scenarios."""
    lines = ["Mock Store Scenarios:"]
    for sid, s in SCENARIOS.items():
        expected = s["expected_outcome"]
        action = expected.get("expected_tool") or "SKIP"
        lines.append(f"  [{sid}] {s['label']}")
        lines.append(f"    → Expected: {action}")
    return "\n".join(lines)
