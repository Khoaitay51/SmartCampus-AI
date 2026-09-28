"""
app/llm/client.py
-----------------
Protocol và Base Interface cho các LLM Client kết nối với ReActXenAgent.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Protocol giao tiếp chuẩn với các LLM Provider (Google Gemini, OpenAI, v.v.)."""

    async def complete(self, system_prompt: str) -> str:
        """Gửi system_prompt tới LLM và nhận chuỗi phản hồi text."""
        ...
