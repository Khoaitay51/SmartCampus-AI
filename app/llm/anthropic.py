"""
app/llm/anthropic.py
-------------------
Client kết nối Anthropic Claude API cho ReActXenAgent.
Hỗ trợ các model như claude-3-5-haiku, claude-3-haiku, haiku5.5, v.v.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any
import httpx

try:
    from app.config.settings import settings
except ImportError:
    settings = None

from app.llm.client import LLMClient

logger = logging.getLogger("app.llm.anthropic")


def _cfg(name: str, default: Any) -> Any:
    return getattr(settings, name, default) if settings else default


def normalize_anthropic_model(model_name: str | None) -> str:
    """Chuẩn hóa tên model Claude / Anthropic."""
    if not model_name:
        return _cfg("ANTHROPIC_MODEL", "claude-haiku-5-5")
    cleaned = model_name.strip()
    low = cleaned.lower()
    if low in {"haiku5.5", "haiku-5.5", "haiku_5_5", "haiku 5.5", "haiku55", "claude-haiku-5-5", "claude-haiku-5.5"}:
        return "claude-haiku-5-5"
    if low in {"haiku", "claude-haiku", "claude-3-5-haiku", "3.5-haiku"}:
        return "claude-haiku-5-5"
    if low in {"sonnet", "claude-3-5-sonnet", "3.5-sonnet", "sonnet 5.5", "sonnet-5.5", "claude-sonnet-5-5"}:
        return "claude-sonnet-5-5"
    return cleaned


class AnthropicLLMClient(LLMClient):
    """Client kết nối Anthropic Claude API cho ReActXenAgent."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: float = 180.0,
    ) -> None:
        self.api_key = (
            api_key
            or _cfg("ANTHROPIC_API_KEY", "")
        )
        raw_model = model or _cfg("ANTHROPIC_MODEL", "claude-haiku-5-5")
        self.model = normalize_anthropic_model(raw_model)
        self.base_url = (
            base_url or _cfg("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        ).rstrip("/")
        self.temperature = (
            temperature
            if temperature is not None
            else _cfg("AGENT_TEMPERATURE", 0.0)
        )
        self.max_tokens = (
            max_tokens
            if max_tokens is not None
            else _cfg("ANTHROPIC_MAX_TOKENS", _cfg("AGENT_LLM_MAX_TOKENS", 4096))
        )
        self.timeout = timeout
        self.stop_sequences = ["Observation:", "\nObservation:"]

        self.total_input_tokens = 0
        self.total_output_tokens = 0

    @property
    def is_modern_model(self) -> bool:
        low = self.model.lower()
        return any(x in low for x in ("5-5", "5.5", "5-2", "5-1", "opus-5", "sonnet-5", "haiku-5", "fable-5"))

    async def complete(self, system_prompt: str) -> str:
        """Gửi prompt tới Anthropic Messages API và nhận text phản hồi."""
        if not self.api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY chưa được cấu hình. Vui lòng thêm ANTHROPIC_API_KEY vào .env"
            )

        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": "Hãy thực hiện bước tiếp theo theo đúng định dạng được yêu cầu.",
                },
            ],
            "max_tokens": self.max_tokens,
            "stop_sequences": self.stop_sequences,
            "thinking": {"type": "disabled"},
        }
        if not self.is_modern_model:
            payload["temperature"] = self.temperature

        max_retries = 4
        backoff_delay = 5.0

        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, headers=headers, json=payload)

                    if resp.status_code in {429, 500, 502, 503, 504, 529}:
                        err_text = resp.text
                        if attempt < max_retries:
                            wait_time = backoff_delay * attempt
                            logger.warning(
                                "Anthropic API trả mã %d (lần %d/%d). Đợi %.1fs rồi retry... Chi tiết: %s",
                                resp.status_code,
                                attempt,
                                max_retries,
                                wait_time,
                                err_text[:200],
                            )
                            await asyncio.sleep(wait_time)
                            continue

                    resp.raise_for_status()
                    data = resp.json()

                    contents = data.get("content") or []
                    text_parts = [c.get("text", "") for c in contents if c.get("type") == "text"]
                    text = "".join(text_parts)

                    usage = data.get("usage") or {}
                    self.total_input_tokens += usage.get("input_tokens", 0)
                    self.total_output_tokens += usage.get("output_tokens", 0)

                    return text

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                if attempt < max_retries:
                    wait_time = backoff_delay * attempt
                    logger.warning(
                        "Lỗi kết nối/timeout với Anthropic API (lần %d/%d): %s. Đợi %.1fs rồi retry...",
                        attempt,
                        max_retries,
                        exc,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)
                    continue
                logger.error("Anthropic API thất bại sau %d lần thử: %s", max_retries, exc)
                raise
            except Exception as exc:
                logger.error("Anthropic complete call thất bại (model=%s): %s", self.model, exc)
                raise


__all__ = ["AnthropicLLMClient", "normalize_anthropic_model"]
