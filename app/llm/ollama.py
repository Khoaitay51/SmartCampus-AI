"""
app/llm/ollama.py
-----------------
Client kết nối Ollama API phục vụ ReActXenAgent với các mô hình SLM (Small Language Models)
như Qwen 1.5B (qwen2:1.5b), Qwen 0.5B, hoặc Llama.
"""
from __future__ import annotations

import logging
from typing import Any
import httpx

try:
    from app.config.settings import settings
except ImportError:
    settings = None

from app.llm.client import LLMClient

logger = logging.getLogger("app.llm.ollama")


def _cfg(name: str, default: Any) -> Any:
    return getattr(settings, name, default) if settings else default


class OllamaLLMClient(LLMClient):
    """Client kết nối trực tiếp với Ollama server cho ReActXenAgent."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        num_ctx: int | None = None,
        timeout: float = 180.0,
    ) -> None:
        self.base_url = (
            base_url or _cfg("OLLAMA_BASE_URL", "http://localhost:11434")
        ).rstrip("/")
        self.model = model or _cfg("OLLAMA_MODEL", "qwen2:1.5b")
        self.temperature = (
            temperature
            if temperature is not None
            else _cfg("AGENT_TEMPERATURE", 0.1)
        )
        self.max_tokens = (
            max_tokens
            if max_tokens is not None
            else _cfg("AGENT_LLM_MAX_TOKENS", 2048)
        )
        self.num_ctx = (
            num_ctx
            if num_ctx is not None
            else _cfg("OLLAMA_NUM_CTX", 16384)
        )
        self.timeout = timeout
        self.stop_sequences = ["Observation:", "\nObservation:"]

    async def complete(self, system_prompt: str) -> str:
        """Gửi prompt tới Ollama và trả về chuỗi text hoàn chỉnh."""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": "Hãy thực hiện ngay bước tiếp theo. Bắt đầu bằng định dạng:\nThought: [suy nghĩ của bạn]\nAction: [tên tool]\nAction Input: {...}",
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
                "num_ctx": self.num_ctx,
                "stop": self.stop_sequences,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                text = data.get("response", "")
                if not text:
                    logger.warning("Ollama (%s) trả về response rỗng", self.model)
                return text
            except httpx.ConnectError as exc:
                logger.error("Không thể kết nối đến Ollama tại %s: %s", self.base_url, exc)
                raise RuntimeError(
                    f"Không kết nối được Ollama tại {self.base_url}. Hãy chắc chắn Ollama container/service đang chạy."
                ) from exc
            except Exception as exc:
                logger.error("Ollama complete call thất bại (model=%s): %s", self.model, exc)
                raise


__all__ = ["OllamaLLMClient"]
