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


async def execute_rag_tool(
    tool_name: str,
    params: dict[str, Any],
    context: Any = None,
    client: GatewayClient | None = None,
) -> str:
    """Thực thi RAG query tool và trả về kết quả quan sát (observation) cho Agent.

    Bắt mọi ngoại lệ về kết nối/tham số và trả về chuỗi thông báo an toàn,
    giúp vòng lặp ReAct của Agent không bị crash khi backend chưa sẵn sàng.
    """
    try:
        gw_client = client or GatewayClient()
        rag = RagClient(gw_client)
        result = await rag.call_tool(tool_name, params)
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        logger.warning("Thực thi RAG tool '%s' thất bại: %s", tool_name, exc)
        return f"Lỗi khi thực thi RAG tool '{tool_name}': {exc}"