"""
mock_backend.py
----------------
FastAPI Mock Server siêu nhẹ giả lập SmartCampus Edge Gateway & RAG API (Port 8000).
Dùng khi bạn muốn test Agent gọi HTTP thực sự sang http://localhost:8000/api
mà không cần dựng database PostgreSQL hay hệ thống cảm biến thật.

Cách chạy:
    python mock_backend.py
"""

from __future__ import annotations

import logging
import sys
from typing import Any
import uvicorn
from fastapi import FastAPI, Query, Request

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [MockBackend] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mock_backend")

app = FastAPI(title="SmartCampus Mock Gateway API", version="1.0.0")


# --- 1. RAG Tools Endpoints ---

@app.get("/api/rag/predict/{room_id}")
async def get_predictions(
    room_id: str,
    metric: str = Query("temperature"),
    horizon: str = Query("15m"),
) -> dict[str, Any]:
    logger.info("--> [GET /rag/predict] room=%s, metric=%s, horizon=%s", room_id, metric, horizon)
    
    # Kịch bản 1: room-temp-trend-check (dự báo nhiệt độ tăng mạnh vượt 34°C)
    if "000000000102" in str(room_id) or "temp" in str(room_id):
        return {
            "room_id": room_id,
            "metric": metric,
            "horizon": horizon,
            "current_value": 30.8,
            "predicted_value": 34.5,
            "trend": "rising",
            "confidence": 0.94,
            "model": "EWMA-v2",
            "analysis": f"CẢNH BÁO EWMA: Nhiệt độ dự báo sẽ tiếp tục tăng vọt từ 30.8°C lên 34.5°C trong {horizon} tới do phòng đang có 35 sinh viên và không có quạt thông gió.",
        }

    if metric == "temperature":
        return {
            "room_id": room_id,
            "metric": metric,
            "horizon": horizon,
            "current_value": 36.2,
            "predicted_value": 37.8,
            "trend": "rising",
            "confidence": 0.92,
            "model": "EWMA-v2",
            "analysis": f"Dự báo nhiệt độ sẽ tiếp tục tăng lên 37.8°C trong {horizon} tới nếu không bật điều hòa.",
        }
    if metric == "co2":
        return {
            "room_id": room_id,
            "metric": metric,
            "horizon": horizon,
            "current_value": 1450.0,
            "predicted_value": 1700.0,
            "trend": "rising",
            "confidence": 0.89,
            "model": "EWMA-v2",
            "analysis": f"Nồng độ CO2 dự báo vượt ngưỡng 1700ppm trong {horizon} tới.",
        }
    return {
        "room_id": room_id,
        "metric": metric,
        "horizon": horizon,
        "current_value": 70.0,
        "predicted_value": 73.0,
        "trend": "stable",
        "confidence": 0.85,
    }


@app.get("/api/rag/telemetry/{room_id}")
async def get_telemetry(
    room_id: str,
    metric: str = Query("temperature"),
    window: str = Query("1h"),
) -> dict[str, Any]:
    logger.info("--> [GET /rag/telemetry] room=%s, metric=%s, window=%s", room_id, metric, window)

    # Kịch bản 1: room-temp-trend-check (nhiệt độ tăng liên tục trong 1h qua)
    if "000000000102" in str(room_id) or "temp" in str(room_id):
        return {
            "room_id": room_id,
            "metric": metric,
            "window": window,
            "latest": 30.8,
            "avg": 28.5,
            "min": 25.2,
            "max": 30.8,
            "trend": "increasing",
            "analysis": "Dữ liệu telemetry 1h qua: Nhiệt độ tăng đều đặn từ 25.2°C lên 30.8°C (+5.6°C), không có dấu hiệu tự hạ nhiệt.",
            "samples_count": 30,
        }

    # Kịch bản 3: room-smoke-first-spike (khói vừa chớm tăng đột biến)
    if "000000000003" in str(room_id) or "smoke" in str(room_id):
        val = 415.0 if metric == "smoke" else 26.2
        return {
            "room_id": room_id,
            "metric": metric,
            "window": window,
            "latest": val,
            "avg": 120.0 if metric == "smoke" else 26.0,
            "min": 40.0 if metric == "smoke" else 25.5,
            "max": val,
            "trend": "sharp_spike" if metric == "smoke" else "stable",
            "analysis": "Chỉ số khói MQ2 tăng vọt từ 60 lên 415 trong 3 phút qua, trong khi nhiệt độ phòng ổn định 26.2°C.",
            "samples_count": 15,
        }

    val = 36.2 if metric == "temperature" else (1450.0 if metric == "co2" else 71.0)
    return {
        "room_id": room_id,
        "metric": metric,
        "window": window,
        "latest": val,
        "avg": round(val * 0.92, 1),
        "min": round(val * 0.82, 1),
        "max": val,
        "trend": "increasing",
        "samples_count": 24,
    }


@app.post("/api/rag/search")
async def search_history(request: Request) -> dict[str, Any]:
    body = await request.json()
    query = body.get("query", "")
    logger.info("--> [POST /rag/search] query='%s'", query)
    return {
        "query": query,
        "results": [
            {
                "event_type": "temperature_anomaly",
                "action_taken": "set_fan",
                "parameters": {"state": "on"},
                "outcome": "Bật quạt thông gió làm mát phòng học đông người, nhiệt độ giảm về 27°C an toàn sau 15 phút.",
                "similarity": 0.92,
            },
            {
                "event_type": "rfid_unknown",
                "action_taken": "send_alert",
                "parameters": {"level": "warning", "message": "Quẹt thẻ lạ ngoài giờ học"},
                "outcome": "Đã gửi thông báo cho bảo vệ xác minh trường hợp sinh viên quên đồ.",
                "similarity": 0.88,
            },
        ],
    }


@app.get("/api/rag/attendance")
async def get_attendance(
    room_id: str | None = None,
    session_id: str | None = None,
    class_code: str | None = None,
) -> dict[str, Any]:
    logger.info("--> [GET /rag/attendance] room=%s, session=%s, class=%s", room_id, session_id, class_code)
    return {
        "room_id": room_id or "room-a101",
        "session_id": session_id or "sess-101",
        "class_code": class_code or "CS101",
        "enrolled_count": 40,
        "checked_in_count": 38,
        "attendance_rate": 0.95,
        "status": "ongoing",
    }


@app.post("/api/rag/compare")
async def compare_rooms(request: Request) -> dict[str, Any]:
    body = await request.json()
    logger.info("--> [POST /rag/compare] body=%s", body)
    room_ids = body.get("room_ids", ["room-a101", "room-a102"])
    return {
        "metric": body.get("metric", "temperature"),
        "window": body.get("window", "1h"),
        "comparisons": [
            {"room_id": r, "value": 30.8 if idx == 0 else 25.0, "status": "anomaly" if idx == 0 else "normal"}
            for idx, r in enumerate(room_ids)
        ],
    }


@app.get("/api/rooms/{room_id}/history")
async def get_room_history(room_id: str, hours: int = 24) -> dict[str, Any]:
    logger.info("--> [GET /rooms/%s/history] hours=%d", room_id, hours)

    # Kịch bản 2: room-rfid-unknown-night (phòng đã khóa từ 17:30 chiều)
    if "000000000204" in str(room_id) or "rfid" in str(room_id):
        return {
            "room_id": room_id,
            "hours": hours,
            "current_state": "LOCKED",
            "transitions": [
                {"timestamp": "2026-09-24T13:00:00Z", "mode": "LECTURE", "trigger": "class_start"},
                {"timestamp": "2026-09-24T17:30:00Z", "mode": "SAVING", "trigger": "class_end_and_lock"},
            ],
            "note": "Phòng đã đóng cửa và chuyển sang SAVING từ 17:30. Không có người ra vào hợp lệ từ đó đến nay.",
        }

    # Kịch bản 3: room-smoke-first-spike (lần đầu phát hiện khói, không có tiền sử 24h)
    if "000000000003" in str(room_id) or "smoke" in str(room_id):
        return {
            "room_id": room_id,
            "hours": hours,
            "smoke_events_past_24h": 0,
            "current_state": "LECTURE",
            "transitions": [
                {"timestamp": "2026-09-24T09:30:00Z", "mode": "LECTURE", "trigger": "class_start"},
            ],
            "note": "24h qua không ghi nhận bất kỳ sự kiện khói nào. Đây là lần đầu tiên cảm biến MQ2 chạm ngưỡng.",
        }

    return {
        "room_id": room_id,
        "hours": hours,
        "transitions": [
            {"timestamp": "2026-09-22T07:00:00+07:00", "mode": "IDLE", "trigger": "schedule"},
            {"timestamp": "2026-09-22T07:30:00+07:00", "mode": "LECTURE", "trigger": "class_start"},
            {"timestamp": "2026-09-22T08:10:00+07:00", "mode": "LECTURE", "trigger": "temp_warning"},
        ],
    }


@app.get("/api/rag/schedule")
async def get_schedule(room_id: str | None = None, date: str | None = None) -> dict[str, Any]:
    logger.info("--> [GET /rag/schedule] room=%s, date=%s", room_id, date)

    # Kịch bản 2: room-rfid-unknown-night (không có lớp học ban đêm)
    if room_id and ("000000000204" in str(room_id) or "rfid" in str(room_id)):
        return {
            "room_id": room_id,
            "date": date or "today",
            "classes_today": [
                {"class_code": "CS101", "start": "07:30", "end": "11:30", "status": "completed"},
                {"class_code": "MATH201", "start": "13:30", "end": "17:30", "status": "completed"},
            ],
            "active_session": None,
            "note": "Phòng A204 không có lịch học buổi tối sau 17:30.",
        }

    return {
        "room_id": room_id or "room-a101",
        "date": date or "today",
        "active_session": {
            "class_code": "CS101",
            "subject": "Nhập môn Hệ thống IoT",
            "lecturer": "TS. Nguyen Van A",
            "start": "07:30",
            "end": "11:30",
            "room_mode": "LECTURE",
        },
    }


# --- 2. Rooms & Telemetry Endpoints ---

@app.get("/api/rooms")
async def list_rooms() -> list[dict[str, Any]]:
    return [
        {"room_id": "a101", "room_name": "Phòng A101", "current_mode": "LECTURE", "room_type": "lecture_hall"},
        {"room_id": "lab202", "room_name": "Phòng Lab 202", "current_mode": "LAB", "room_type": "laboratory"},
        {"room_id": "b301", "room_name": "Phòng Hội thảo B301", "current_mode": "IDLE", "room_type": "meeting_room"},
    ]


@app.get("/api/rooms/{room_id}")
async def get_room(room_id: str) -> dict[str, Any]:
    return {
        "room_id": room_id,
        "room_name": f"Phòng {room_id.upper()}",
        "room_type": "lecture_hall",
        "current_mode": "LECTURE",
        "smoke_state": "normal",
    }


@app.get("/api/telemetry/{room_id}/latest")
async def get_latest_telemetry(room_id: str) -> dict[str, Any]:
    return {
        "room_id": room_id,
        "temperature": 36.2,
        "humidity": 71.0,
        "co2": 1450.0,
        "smoke_value": 0.0,
        "air_quality": 58.0,
    }


if __name__ == "__main__":
    print("=================================================================")
    print(" SmartCampus Mock Backend Gateway API đang chạy tại:")
    print("   --> http://localhost:8000/api")
    print(" Bấm Ctrl+C để dừng.")
    print("=================================================================")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
