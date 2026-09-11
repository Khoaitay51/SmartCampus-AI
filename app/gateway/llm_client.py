"""
gateway/llm_client.py
------------------------
Wrapper gọi LLM (Claude) cho agent/agent.py — implement vòng lặp ReAct
(Observe → Think → Act) mô tả ở section 3d.

Luồng dùng trong agent.py:
1. Gửi operational_context + event cho LLM kèm RAG_TOOL_SCHEMAS.
2. Nếu response có tool_use block → gọi RagClient.call_tool(...) tương ứng
   (rag.py tự enforce budget 5 call/evaluation).
3. Gửi kết quả tool trở lại LLM (build_tool_result_message), lặp lại cho tới
   khi LLM trả text cuối cùng — kỳ vọng là JSON recommendation theo
   schemas/recommendation.py.

Rule 8 (section 7): "RAG output sanitization — kết quả RAG có thể chứa
user-generated content. Không inject trực tiếp vào system prompt."
→ Nên chạy qua safety/validation.py trước khi đưa vào build_tool_result_message.
"""
from __future__ import annotations

import json
import logging
from typing import Any

try:
    from anthropic import AsyncAnthropic
except ImportError:
    AsyncAnthropic = None

try:
    from app.config.settings import settings
except ImportError:
    settings = None

logger = logging.getLogger("agent.gateway.llm_client")


def _cfg(name: str, default: Any) -> Any:
    return getattr(settings, name, default) if settings else default


RAG_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "search_history",
        "description": "Semantic search qua pgvector embeddings trên telemetry summaries lịch sử.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "room_id": {"type": ["string", "null"]},
                "time_range": {"type": "string", "enum": ["1h", "6h", "24h", "7d"]},
            },
            "required": ["query", "time_range"],
        },
    },
    {
        "name": "get_telemetry",
        "description": "Query raw time-series data cho 1 metric cụ thể của 1 phòng.",
        "input_schema": {
            "type": "object",
            "properties": {
                "room_id": {"type": "string"},
                "metric": {"type": "string", "enum": ["temperature", "humidity", "co2", "smoke", "occupancy"]},
                "window": {"type": "string", "enum": ["15m", "1h", "6h"]},
            },
            "required": ["room_id", "metric", "window"],
        },
    },
    {
        "name": "get_attendance",
        "description": "Query attendance records theo phòng/session/lớp.",
        "input_schema": {
            "type": "object",
            "properties": {
                "room_id": {"type": ["string", "null"]},
                "session_id": {"type": ["string", "null"]},
                "class_code": {"type": ["string", "null"]},
            },
        },
    },
    {
        "name": "compare_rooms",
        "description": "So sánh 1 metric giữa nhiều phòng trong 1 khoảng thời gian.",
        "input_schema": {
            "type": "object",
            "properties": {
                "room_ids": {"type": "array", "items": {"type": "string"}},
                "metric": {"type": "string"},
                "window": {"type": "string", "enum": ["1h", "6h", "24h"]},
            },
            "required": ["room_ids", "metric", "window"],
        },
    },
    {
        "name": "get_room_history",
        "description": "Lịch sử state transitions (FSM) của 1 phòng.",
        "input_schema": {
            "type": "object",
            "properties": {"room_id": {"type": "string"}, "hours": {"type": "integer"}},
            "required": ["room_id", "hours"],
        },
    },
    {
        "name": "get_schedule",
        "description": "Query lịch học theo phòng hoặc theo ngày.",
        "input_schema": {
            "type": "object",
            "properties": {
                "room_id": {"type": ["string", "null"]},
                "date": {"type": ["string", "null"]},
            },
        },
    },
    {
        "name": "get_predictions",
        "description": "EWMA prediction cho 1 metric trong tương lai gần.",
        "input_schema": {
            "type": "object",
            "properties": {
                "room_id": {"type": "string"},
                "metric": {"type": "string", "enum": ["temperature", "co2"]},
                "horizon": {"type": "string", "enum": ["15m", "30m"]},
            },
            "required": ["room_id", "metric", "horizon"],
        },
    },
]


class LLMClient:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        effective_key = api_key or _cfg("ANTHROPIC_API_KEY", None)
        self.model = model or _cfg("AGENT", _cfg("AGENT_LLM_MODEL", "claude-3-7-sonnet-20250219"))
        self.max_tokens = _cfg("AGENT_LLM_MAX_TOKENS", 1500)
        if AsyncAnthropic is None:
            self._client = None
        elif effective_key:
            self._client = AsyncAnthropic(api_key=effective_key)
        else:
            # Cho phép khởi tạo client khi chưa config API key (tránh crash lúc khởi động hoặc test)
            self._client = AsyncAnthropic(api_key="sk-ant-dummy-placeholder-key")

    async def complete(self, system_prompt: str) -> str:
        """Gửi system_prompt và trả về kết quả text hoàn chỉnh cho ReActXenAgent (ReAct/Review/Reflect)."""
        if self._client is None:
            raise RuntimeError("Thư viện 'anthropic' chưa được cài đặt trong môi trường. Vui lòng cài đặt: pip install anthropic")
        try:
            resp = await self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": "Hãy thực hiện bước tiếp theo theo đúng định dạng được yêu cầu.",
                    }
                ],
            )
            return self.extract_text(resp)
        except Exception as exc:
            logger.error("LLM complete call thất bại: %s", exc)
            raise

    async def react_step(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> Any:
        """Gửi 1 lượt tới LLM kèm RAG tool schemas.

        Trả về response object gốc của Anthropic SDK — agent.py tự parse content
        blocks (có thể là tool_use hoặc text JSON cuối cùng) bằng extract_tool_uses
        / extract_text bên dưới.
        """
        if self._client is None:
            raise RuntimeError("Thư viện 'anthropic' chưa được cài đặt trong môi trường. Vui lòng cài đặt: pip install anthropic")
        try:
            return await self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=messages,
                tools=RAG_TOOL_SCHEMAS,
            )
        except Exception as exc:  # noqa: BLE001 - agent cần fallback an toàn khi LLM lỗi
            logger.error("LLM call thất bại: %s", exc)
            raise

    @staticmethod
    def extract_tool_uses(response: Any) -> list[dict[str, Any]]:
        """Lấy các tool_use block từ response, dùng cho agent.py điều phối RAG call."""
        return [
            {"id": block.id, "name": block.name, "input": block.input}
            for block in response.content
            if getattr(block, "type", None) == "tool_use"
        ]

    @staticmethod
    def extract_text(response: Any) -> str:
        """Lấy phần text (kỳ vọng là JSON recommendation cuối cùng) từ response."""
        parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        return "\n".join(parts)

    @staticmethod
    def build_tool_result_message(tool_use_id: str, result: dict[str, Any]) -> dict[str, Any]:
        """Build message role=user chứa tool_result để gửi lại LLM, tiếp vòng ReAct."""
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": json.dumps(result, ensure_ascii=False)[:4000],
                }
            ],
        }


# Alias cho phép import bằng cả hai tên
AnthropicLLMClient = LLMClient

__all__ = ["LLMClient", "AnthropicLLMClient", "RAG_TOOL_SCHEMAS"]