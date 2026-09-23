"""
gateway/llm_client.py
------------------------
Wrapper gọi LLM (Google Gemini) cho agent/agent.py — implement giao tiếp
với ReActXenAgent qua method complete().
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

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
    """Client kết nối Google Gemini API cho ReActXenAgent."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        effective_key = api_key or _cfg("GEMINI_API_KEY", None)
        self.model = model or _cfg("AGENT", _cfg("GEMINI_MODEL", "gemini-3.6-flash"))
        self.max_tokens = _cfg("AGENT_LLM_MAX_TOKENS", 1500)
        self.temperature = _cfg("AGENT_TEMPERATURE", 0.1)

        if genai is None:
            self._client = None
        elif effective_key:
            self._client = genai.Client(api_key=effective_key)
        else:
            # Cho phép khởi tạo client khi chưa config API key (tránh crash lúc khởi động hoặc test)
            self._client = genai.Client(api_key="dummy-gemini-key")

    async def complete(self, system_prompt: str) -> str:
        """Gửi system_prompt và trả về kết quả text hoàn chỉnh cho ReActXenAgent (ReAct/Review/Reflect)."""
        if self._client is None or types is None:
            raise RuntimeError(
                "Thư viện 'google-genai' chưa được cài đặt trong môi trường. Vui lòng chạy: pip install google-genai"
            )
        max_retries = 2 # Do request nhiều thì limit gemini không đủ nên để là 2: chuẩn thì nên cho lên 3
        backoff_delay = 6.0
        for attempt in range(1, max_retries + 1):
            try:
                config = types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                )
                response = await self._client.aio.models.generate_content(
                    model=self.model,
                    contents="Hãy thực hiện bước tiếp theo theo đúng định dạng được yêu cầu.",
                    config=config,
                )
                return response.text or ""
            except Exception as exc:
                err_msg = str(exc)
                if ("429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "Quota exceeded" in err_msg) and attempt < max_retries:
                    wait_time = backoff_delay * attempt
                    logger.warning(
                        "Gemini API rate limit 429 hit (lần %d/%d). Vượt quá quota Free Tier, tự động đợi %.1fs trước khi retry...",
                        attempt, max_retries, wait_time
                    )
                    await asyncio.sleep(wait_time)
                    continue
                logger.error("Gemini complete call thất bại: %s", exc)
                raise


# Alias định danh rõ ràng
GeminiLLMClient = LLMClient

__all__ = ["LLMClient", "GeminiLLMClient", "RAG_TOOL_SCHEMAS"]