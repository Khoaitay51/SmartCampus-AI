"""
app/llm/deepseek.py
-------------------
Client kết nối trực tiếp DeepSeek API (OpenAI-compatible) cho ReActXenAgent.
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

logger = logging.getLogger("app.llm.deepseek")


def _cfg(name: str, default: Any) -> Any:
    return getattr(settings, name, default) if settings else default


def normalize_deepseek_model(model_name: str | None) -> str:
    """Chuẩn hóa tên model DeepSeek, hỗ trợ alias như 'deepseek 4.1 flash' -> 'deepseek-flash'."""
    if not model_name:
        return _cfg("DEEPSEEK_MODEL", "deepseek-flash")
    cleaned = model_name.strip().lower()
    if cleaned in {
        "deepseek 4.1 flash",
        "deepseek-4.1-flash",
        "deepseek_4_1_flash",
        "deepseek_flash",
        "deepseek-flash",
        "4.1 flash",
        "4.1-flash",
        "4.1_flash",
    }:
        return "deepseek-flash"
    return model_name.strip()


class DeepSeekLLMClient(LLMClient):
    """Client kết nối trực tiếp DeepSeek API cho ReActXenAgent."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: float = 180.0,
        reasoning_effort: str | None = None,
    ) -> None:
        self.api_key = (
            api_key
            or _cfg("DEEPSEEK_API_KEY", "")
        )
        raw_model = model or _cfg("DEEPSEEK_MODEL", "deepseek-flash")
        self.model = normalize_deepseek_model(raw_model)
        self.base_url = (
            base_url or _cfg("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        ).rstrip("/")
        self.temperature = (
            temperature
            if temperature is not None
            else _cfg("AGENT_TEMPERATURE", 0.0)
        )
        self.max_tokens = (
            max_tokens
            if max_tokens is not None
            else _cfg("DEEPSEEK_MAX_TOKENS", _cfg("AGENT_LLM_MAX_TOKENS", 4096))
        )
        self.reasoning_effort = (
            reasoning_effort
            if reasoning_effort is not None
            else _cfg("DEEPSEEK_REASONING_EFFORT", "none")
        )
        self.timeout = timeout
        self.stop_sequences = ["Observation:", "\nObservation:"]

        self.total_input_tokens = 0
        self.total_output_tokens = 0

    async def complete(self, system_prompt: str) -> str:
        """Gửi system_prompt tới DeepSeek chat completions API và nhận kết quả text."""
        if not self.api_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY chưa được cấu hình. Vui lòng thêm DEEPSEEK_API_KEY vào .env"
            )

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "Hãy thực hiện bước tiếp theo theo đúng định dạng được yêu cầu.",
                },
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stop": self.stop_sequences,
            "stream": False,
        }
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort

        max_retries = 4
        backoff_delay = 5.0

        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, headers=headers, json=payload)

                    if resp.status_code in {429, 500, 502, 503, 504}:
                        err_text = resp.text
                        if attempt < max_retries:
                            wait_time = backoff_delay * attempt
                            logger.warning(
                                "DeepSeek API trả mã %d (lần %d/%d). Đợi %.1fs rồi retry... Chi tiết: %s",
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

                    choices = data.get("choices") or []
                    if not choices:
                        logger.warning("DeepSeek API (%s) trả về choices rỗng", self.model)
                        return ""

                    msg = choices[0].get("message") or {}
                    content = msg.get("content") or ""

                    usage = data.get("usage") or {}
                    self.total_input_tokens += usage.get("prompt_tokens", 0)
                    self.total_output_tokens += usage.get("completion_tokens", 0)

                    return content

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                if attempt < max_retries:
                    wait_time = backoff_delay * attempt
                    logger.warning(
                        "Lỗi kết nối/timeout với DeepSeek API (lần %d/%d): %s. Đợi %.1fs rồi retry...",
                        attempt,
                        max_retries,
                        exc,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)
                    continue
                logger.error("DeepSeek API thất bại sau %d lần thử: %s", max_retries, exc)
                raise
            except Exception as exc:
                logger.error("DeepSeek complete call thất bại (model=%s): %s", self.model, exc)
                raise


__all__ = ["DeepSeekLLMClient", "normalize_deepseek_model"]
