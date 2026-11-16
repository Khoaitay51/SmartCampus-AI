"""
app/llm/openai.py
-----------------
Client kết nối OpenAI API (hoặc OpenAI-compatible gateway) cho ReActXenAgent.
Hỗ trợ các model như gpt-6-luna, gpt-5.6-luna, gpt-4o, gpt-4o-mini, v.v.
Tương thích chuẩn hiện đại: tự động dùng max_completion_tokens, thích ứng reasoning_effort,
và lọc bỏ stop/temperature với các model thế hệ mới (gpt-6, gpt-5, o1, o3).
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

logger = logging.getLogger("app.llm.openai")


def _cfg(name: str, default: Any) -> Any:
    return getattr(settings, name, default) if settings else default


def normalize_openai_model(model_name: str | None) -> str:
    """Chuẩn hóa tên model OpenAI / GPT."""
    if not model_name:
        return _cfg("OPENAI_MODEL", "gpt-6-luna")
    cleaned = model_name.strip()
    low = cleaned.lower()
    if low in {"gpt 6 luna", "gpt-6-luna", "gpt_6_luna", "gpt 6-luna", "luna", "gpt_luna"}:
        return "gpt-6-luna"
    if low in {"gpt 5.6 luna", "gpt-5.6-luna", "gpt_5.6_luna", "gpt 5.6-luna", "gpt-5.6", "5.6-luna"}:
        return "gpt-5.6-luna"
    if low in {"gpt-4o", "gpt_4o", "4o"}:
        return "gpt-4o"
    if low in {"gpt-4o-mini", "gpt_4o_mini", "4o-mini"}:
        return "gpt-4o-mini"
    return cleaned


class OpenAILLMClient(LLMClient):
    """Client kết nối OpenAI / GPT API cho ReActXenAgent."""

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
            or _cfg("OPENAI_API_KEY", "")
        )
        raw_model = model or _cfg("OPENAI_MODEL", "gpt-6-luna")
        self.model = normalize_openai_model(raw_model)
        self.base_url = (
            base_url or _cfg("OPENAI_BASE_URL", "https://api.openai.com/v1")
        ).rstrip("/")
        self.temperature = (
            temperature
            if temperature is not None
            else _cfg("AGENT_TEMPERATURE", 0.0)
        )
        self.max_tokens = (
            max_tokens
            if max_tokens is not None
            else _cfg("OPENAI_MAX_TOKENS", _cfg("AGENT_LLM_MAX_TOKENS", 4096))
        )
        self.timeout = timeout
        self.stop_sequences = ["Observation:", "\nObservation:"]
        self.reasoning_effort = (
            reasoning_effort
            if reasoning_effort is not None
            else _cfg("OPENAI_REASONING_EFFORT", "none")
        )

        self.total_input_tokens = 0
        self.total_output_tokens = 0

    @property
    def is_modern_model(self) -> bool:
        low = self.model.lower()
        return any(low.startswith(p) for p in ("gpt-6", "gpt-5", "o1", "o3", "o4"))

    async def complete(self, system_prompt: str) -> str:
        """Gửi system_prompt tới OpenAI chat completions API và nhận text phản hồi."""
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY chưa được cấu hình. Vui lòng thêm OPENAI_API_KEY vào .env"
            )

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Payload tương thích cho cả model hiện đại (gpt-6/gpt-5/o1/o3) và legacy
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "Hãy thực hiện bước tiếp theo theo đúng định dạng được yêu cầu.",
                },
            ],
            "max_completion_tokens": self.max_tokens,
            "stream": False,
        }

        if self.is_modern_model:
            # Model hiện đại: không gửi stop hoặc temperature = 0.0 (sẽ bị 400 Bad Request)
            if self.reasoning_effort:
                payload["reasoning_effort"] = self.reasoning_effort
        else:
            payload["temperature"] = self.temperature
            payload["stop"] = self.stop_sequences

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
                                "OpenAI API trả mã %d (lần %d/%d). Đợi %.1fs rồi retry... Chi tiết: %s",
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
                        logger.warning("OpenAI API (%s) trả về choices rỗng", self.model)
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
                        "Lỗi kết nối/timeout với OpenAI API (lần %d/%d): %s. Đợi %.1fs rồi retry...",
                        attempt,
                        max_retries,
                        exc,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)
                    continue
                logger.error("OpenAI API thất bại sau %d lần thử: %s", max_retries, exc)
                raise
            except Exception as exc:
                logger.error("OpenAI complete call thất bại (model=%s): %s", self.model, exc)
                raise


__all__ = ["OpenAILLMClient", "normalize_openai_model"]
