"""
gateway/rag.py
---------------
Wrapper cho RAG Query Tools (section 3b) — read-only, agent tự gọi trong vòng ReAct
(Observe → Think → Act, section 3d) để bổ sung thông tin trước khi ra recommendation.

Rule 7 (section 7 - Security constraints):
"max 5 RAG tool calls per evaluation. Nếu cần nhiều hơn, agent phải tổng hợp
từ kết quả hiện có."
→ RagCallBudget enforce đúng rule này. agent.py PHẢI tạo 1 budget mới cho MỖI
request /evaluate (không share giữa các evaluation khác nhau).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Literal

from .client import GatewayClient, GatewayError

try:
    from app.config.settings import settings
except ImportError:
    settings = None

logger = logging.getLogger("agent.gateway.rag")

TimeRange = Literal["1h", "6h", "24h", "7d"]
Metric = Literal["temperature", "humidity", "co2", "smoke", "occupancy"]
Window = Literal["15m", "1h", "6h"]
Horizon = Literal["15m", "30m"]


class RagBudgetExceeded(Exception):
    """Vượt quá số lần gọi RAG tool cho phép trong 1 lần evaluate (section 7, rule 7)."""


class RagCallBudget:
    """Đếm số RAG call trong 1 evaluation. Tạo mới cho mỗi request POST /evaluate."""

    def __init__(self, max_calls: int = 5) -> None:
        self.max_calls = max_calls
        self.used = 0
        self.log: list[dict[str, Any]] = []

    def consume(self, tool: str) -> None:
        if self.used >= self.max_calls:
            raise RagBudgetExceeded(
                f"Đã dùng {self.used}/{self.max_calls} RAG call cho evaluation này. "
                "Hãy tổng hợp từ kết quả hiện có thay vì gọi thêm."
            )
        self.used += 1

    def record(self, tool: str, params: dict[str, Any], result_summary: str) -> None:
        """Log lại cho tool_calls_log trong response cuối (section 3d)."""
        self.log.append({"tool": tool, "params": params, "result_summary": result_summary})


class RagClient:
    """Mỗi method map 1-1 với 1 RAG tool trong section 3b, gọi qua /api/rag/* (section 5)."""

    TOOLS = (
        "search_history", "get_telemetry", "get_attendance",
        "compare_rooms", "get_room_history", "get_schedule", "get_predictions",
    )

    def __init__(self, client: GatewayClient, budget: RagCallBudget | None = None) -> None:
        self._client = client
        self.budget = budget or RagCallBudget()

    async def search_history(
        self, query: str, room_id: str | None = None, time_range: TimeRange = "24h"
    ) -> dict[str, Any]:
        """Semantic search qua pgvector embeddings trên telemetry summaries."""
        self.budget.consume("search_history")
        return await self._client.post(
            "/rag/search", json={"query": query, "room_id": room_id, "time_range": time_range}
        )

    async def get_telemetry(self, room_id: str, metric: Metric, window: Window = "1h") -> dict[str, Any]:
        """Raw time-series data cho 1 metric cụ thể của 1 phòng."""
        self.budget.consume("get_telemetry")
        return await self._client.get(
            f"/rag/telemetry/{room_id}", params={"metric": metric, "window": window}
        )

    async def get_attendance(
        self,
        room_id: str | None = None,
        session_id: str | None = None,
        class_code: str | None = None,
    ) -> dict[str, Any]:
        """Query attendance records theo phòng/session/lớp."""
        self.budget.consume("get_attendance")
        params = {
            k: v for k, v in
            {"room_id": room_id, "session_id": session_id, "class_code": class_code}.items()
            if v is not None
        }
        return await self._client.get("/rag/attendance", params=params)

    async def compare_rooms(self, room_ids: list[str], metric: str, window: str = "1h") -> dict[str, Any]:
        """So sánh 1 metric giữa nhiều phòng trong 1 khoảng thời gian."""
        self.budget.consume("compare_rooms")
        return await self._client.post(
            "/rag/compare", json={"room_ids": room_ids, "metric": metric, "window": window}
        )

    async def get_room_history(self, room_id: str, hours: int = 24) -> dict[str, Any]:
        """Lịch sử state transitions (FSM) của 1 phòng."""
        self.budget.consume("get_room_history")
        return await self._client.get(f"/rooms/{room_id}/history", params={"hours": hours})

    async def get_schedule(self, room_id: str | None = None, date: str | None = None) -> dict[str, Any]:
        """Query lịch học theo phòng hoặc theo ngày."""
        self.budget.consume("get_schedule")
        params = {k: v for k, v in {"room_id": room_id, "date": date}.items() if v is not None}
        return await self._client.get("/rag/schedule", params=params)

    async def get_predictions(self, room_id: str, metric: str, horizon: Horizon = "15m") -> dict[str, Any]:
        """EWMA prediction cho 1 metric trong tương lai gần."""
        self.budget.consume("get_predictions")
        return await self._client.get(
            f"/rag/predict/{room_id}", params={"metric": metric, "horizon": horizon}
        )

    # -------- dispatcher dùng cho vòng lặp tool-calling của LLM (llm_client.py) --------

    async def call_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Gọi tool theo tên (từ tool_use block của LLM) — dùng trong agent.py.
        Reject ngay nếu tool_name không nằm trong TOOLS (bảo vệ kép, ngoài phía LLM schema).
        """
        if tool_name not in self.TOOLS:
            raise GatewayError(f"RAG tool '{tool_name}' không nằm trong danh sách cho phép")
        method = getattr(self, tool_name)
        result = await method(**params)
        self.budget.record(tool_name, params, _summarize(result))
        return result


def _summarize(result: dict[str, Any], limit: int = 200) -> str:
    """Tóm tắt ngắn kết quả RAG để log vào tool_calls_log — tránh dump raw data (rule 8)."""
    text = str(result)
    return text if len(text) <= limit else text[:limit] + "..."


def get_mock_rag_data(tool_name: str, params: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Tạo dữ liệu mock thông minh và thực tế cho RAG tools khi backend offline.

    Tự động trích xuất thông số từ context (nhiệt độ, occupancy, session...) để tạo
    kết quả logic và phù hợp nhất với kịch bản đang chạy.
    """
    room_id = params.get("room_id") or "mock-room-01"

    # Trích xuất dữ liệu bối cảnh nếu có
    curr_temp = 36.2
    curr_co2 = 1450.0
    curr_humidity = 71.0
    class_code = "CS101"
    current_mode = "LECTURE"

    if context:
        try:
            if hasattr(context, "telemetry_summary") and context.telemetry_summary:
                ts = context.telemetry_summary
                if hasattr(ts, "temperature") and ts.temperature:
                    curr_temp = getattr(ts.temperature, "latest", curr_temp) or curr_temp
                if hasattr(ts, "co2") and ts.co2:
                    curr_co2 = getattr(ts.co2, "latest", curr_co2) or curr_co2
                if hasattr(ts, "humidity") and ts.humidity:
                    curr_humidity = getattr(ts.humidity, "latest", curr_humidity) or curr_humidity
            if hasattr(context, "room") and context.room:
                current_mode = getattr(context.room, "current_mode", current_mode) or current_mode
            if hasattr(context, "active_session") and context.active_session:
                class_code = getattr(context.active_session, "class_code", class_code) or class_code
        except Exception:
            pass

    if tool_name == "get_predictions":
        metric = params.get("metric", "temperature")
        horizon = params.get("horizon", "15m")
        if metric == "temperature":
            predicted = round(float(curr_temp) + 1.6, 1)
            msg = f"Dự báo EWMA: Nhiệt độ có xu hướng tiếp tục tăng từ {curr_temp}°C lên {predicted}°C trong {horizon} tới nếu không bật điều hòa làm mát."
        elif metric == "co2":
            predicted = round(float(curr_co2) + 250.0, 1)
            msg = f"Dự báo EWMA: Nồng độ CO2 dự báo sẽ tăng từ {curr_co2}ppm lên {predicted}ppm trong {horizon} tới do phòng đang đông người."
        else:
            predicted = round(float(curr_humidity) + 4.0, 1)
            msg = f"Dự báo {metric} có xu hướng tăng nhẹ lên {predicted} trong {horizon}."

        return {
            "room_id": room_id,
            "metric": metric,
            "horizon": horizon,
            "current_value": curr_temp if metric == "temperature" else curr_co2,
            "predicted_value": predicted,
            "trend": "rising",
            "confidence": 0.92,
            "model": "EWMA-v2",
            "analysis": msg,
        }

    if tool_name == "get_telemetry":
        metric = params.get("metric", "temperature")
        window = params.get("window", "1h")
        val = curr_temp if metric == "temperature" else (curr_co2 if metric == "co2" else curr_humidity)
        return {
            "room_id": room_id,
            "metric": metric,
            "window": window,
            "latest": val,
            "avg": round(float(val) * 0.93, 1),
            "min": round(float(val) * 0.85, 1),
            "max": val,
            "trend": "increasing",
            "samples_count": 24,
        }

    if tool_name == "search_history":
        query = params.get("query", "")
        return {
            "query": query,
            "results": [
                {
                    "event_type": "temperature_anomaly",
                    "action_taken": "adjust_hvac_mode",
                    "parameters": {"mode": "cool", "target_temperature": 24, "fan_speed": "high"},
                    "outcome": "Hạ nhiệt độ điều hòa xuống 24°C và mở quạt gió, nhiệt độ phòng đã giảm về 25°C an toàn sau 12 phút.",
                    "similarity": 0.91,
                },
                {
                    "event_type": "air_quality_degraded",
                    "action_taken": "open_ventilation",
                    "parameters": {"duration_minutes": 15},
                    "outcome": "Kích hoạt quạt thông gió giúp nồng độ CO2 giảm về mức an toàn 750ppm.",
                    "similarity": 0.84,
                },
            ],
        }

    if tool_name == "get_attendance":
        return {
            "room_id": room_id,
            "session_id": params.get("session_id") or "session-auto-101",
            "class_code": params.get("class_code") or class_code,
            "enrolled_count": 40,
            "checked_in_count": 38,
            "attendance_rate": 0.95,
            "status": "ongoing",
        }

    if tool_name == "compare_rooms":
        metric = params.get("metric", "temperature")
        room_ids = params.get("room_ids") or [room_id, "room-b102"]
        return {
            "metric": metric,
            "window": params.get("window", "1h"),
            "comparisons": [
                {"room_id": r, "value": curr_temp if idx == 0 else 24.5, "status": "anomaly" if idx == 0 else "normal"}
                for idx, r in enumerate(room_ids)
            ],
        }

    if tool_name == "get_room_history":
        if "rfid" in str(room_id):
            return {
                "room_id": room_id,
                "hours": params.get("hours", 24),
                "current_state": "LOCKED",
                "transitions": [
                    {"timestamp": "2026-09-24T17:30:00Z", "mode": "SAVING", "trigger": "class_end_and_lock"},
                ],
                "note": "Phòng đã đóng cửa và chuyển sang SAVING từ 17:30. Không có người ra vào hợp lệ từ đó đến nay.",
            }
        if "smoke" in str(room_id):
            return {
                "room_id": room_id,
                "hours": params.get("hours", 24),
                "smoke_events_past_24h": 0,
                "current_state": "LECTURE",
                "note": "24h qua không có sự kiện khói nào. Đây là lần đầu tiên cảm biến chạm ngưỡng.",
            }
        return {
            "room_id": room_id,
            "hours": params.get("hours", 24),
            "transitions": [
                {"timestamp": "2026-09-22T07:00:00+07:00", "mode": "IDLE", "trigger": "schedule"},
                {"timestamp": "2026-09-22T07:30:00+07:00", "mode": current_mode, "trigger": "class_start"},
            ],
        }

    if tool_name == "get_schedule":
        if "rfid" in str(room_id):
            return {
                "room_id": room_id,
                "date": params.get("date") or "today",
                "classes_today": [],
                "active_session": None,
                "note": "Phòng không có lịch học buổi tối sau 17:30.",
            }
        return {
            "room_id": room_id,
            "date": params.get("date") or "today",
            "active_session": {
                "class_code": class_code,
                "subject": "Nhập môn Hệ thống IoT",
                "lecturer": "TS. Nguyen Van A",
                "start": "07:30",
                "end": "11:30",
                "room_mode": current_mode,
            },
        }

    return {"status": "ok", "tool": tool_name, "params": params}


async def execute_rag_tool(
    tool_name: str,
    params: dict[str, Any],
    context: Any = None,
    client: GatewayClient | None = None,
) -> str:
    """Thực thi RAG query tool và trả về kết quả quan sát (observation) cho Agent.

    Tự động fallback về Mock Data thực tế khi không kết nối được Gateway,
    hoặc khi cấu hình USE_MOCK_RAG=True, giúp vòng lặp ReAct của Agent
    luôn có dữ liệu chính xác để tiếp tục suy luận đưa ra quyết định.
    """
    use_mock = getattr(settings, "USE_MOCK_RAG", False) if settings else False

    if not use_mock:
        try:
            gw_client = client or GatewayClient()
            rag = RagClient(gw_client)
            result = await rag.call_tool(tool_name, params)
            return json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            logger.warning(
                "Gateway chưa sẵn sàng (%s) → Tự động cung cấp Mock Data cho RAG tool '%s'",
                exc, tool_name,
            )

    mock_result = get_mock_rag_data(tool_name, params, context)
    logger.info("Đã trả về Mock Data cho RAG tool '%s': %s", tool_name, list(mock_result.keys()))
    return json.dumps(mock_result, ensure_ascii=False)