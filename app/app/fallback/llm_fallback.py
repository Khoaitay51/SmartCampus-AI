"""
fallback/llm_fallback.py
------------------------
CẤP 1 — Model Fallback.

FallbackLLMClient có cùng giao diện với LLMClient (`await complete(system_prompt) -> str`)
nên thay thế được ở chỗ agent đang gọi, không phải sửa agent:

    Gemini chính  ->  Gemini nhỏ/rẻ hơn  ->  Ollama nội bộ (tuỳ chọn)

Mỗi provider có 1 CircuitBreaker riêng: khi provider chính lỗi liên tục thì các
request sau đi thẳng xuống provider phụ, không chờ timeout nữa.
Khi tất cả provider đều hỏng => raise AllProvidersFailed để orchestrator chuyển
xuống CẤP 4 (rule-based).
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from .circuit_breaker import CircuitBreaker
from .trace import LEVEL_MODEL, record

logger = logging.getLogger("agent.fallback.llm")

_CONTENTS = "Hãy thực hiện bước tiếp theo theo đúng định dạng được yêu cầu."

_TRANSIENT_MARKERS = (
    "429", "500", "502", "503", "504", "resource_exhausted", "quota", "unavailable",
    "overloaded", "deadline", "timeout", "timed out", "connection", "getaddrinfo",
    "temporarily", "connecterror", "readerror",
)


class SupportsComplete(Protocol):
    async def complete(self, system_prompt: str) -> str: ...


class AllProvidersFailed(RuntimeError):
    def __init__(self, errors: list[tuple[str, str]]) -> None:
        self.errors = errors
        super().__init__("Tất cả LLM provider đều thất bại: " + "; ".join(f"{n}: {e}" for n, e in errors))


def is_transient_error(exc: BaseException) -> bool:
    """Lỗi hạ tầng (quá tải, mạng, timeout) -> tính vào circuit breaker.
    Lỗi kiểu 400/401 (prompt/key sai) vẫn thử provider kế tiếp nhưng KHÔNG làm ngắt mạch."""
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError, ConnectionError, OSError)):
        return True
    text = f"{type(exc).__name__} {exc}".lower()
    return any(m in text for m in _TRANSIENT_MARKERS)


_STRICT_FOOTER = """

---
QUY TẮC BẮT BUỘC (mô hình dự phòng):
- Chỉ trả về ĐÚNG định dạng đã yêu cầu ở trên. Không thêm lời giải thích, không dùng markdown.
- Nếu trả JSON: chỉ 1 JSON object hợp lệ, đóng đủ ngoặc, không chú thích.
- Nếu không chắc, ưu tiên hành động an toàn và hạ confidence."""


def adapt_prompt_for_small_model(prompt: str, max_chars: int = 6000) -> str:
    """Model nhỏ tuân thủ format kém và context ngắn: cắt phần giữa (giữ hướng dẫn đầu +
    observation gần nhất ở cuối) và thêm footer nhắc format."""
    if len(prompt) > max_chars:
        head = int(max_chars * 0.35)
        tail = max_chars - head
        prompt = prompt[:head] + "\n...[đã lược bớt phần giữa]...\n" + prompt[-tail:]
    return prompt + _STRICT_FOOTER


class OllamaClient:
    """LLM nội bộ (Cloud-to-Local). Trong Docker nên đặt OLLAMA_BASE_URL=http://host.docker.internal:11434."""

    def __init__(
        self, model: str, base_url: str | None = None, temperature: float = 0.1,
        max_tokens: int = 1500, timeout: float = 90.0,
    ) -> None:
        self.model = model
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    async def complete(self, system_prompt: str) -> str:
        import httpx

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "system": system_prompt,
                    "prompt": _CONTENTS,
                    "stream": False,
                    "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
                },
            )
            resp.raise_for_status()
            return resp.json().get("response", "")


@dataclass
class ProviderSpec:
    name: str
    client: SupportsComplete
    breaker: CircuitBreaker
    timeout: float = 30.0
    prompt_adapter: Callable[[str], str] | None = None


@dataclass
class FallbackLLMClient:
    providers: list[ProviderSpec] = field(default_factory=list)
    last_provider: str | None = None

    async def complete(self, system_prompt: str) -> str:
        errors: list[tuple[str, str]] = []

        for idx, p in enumerate(self.providers):
            if not p.breaker.allow_request():
                errors.append((p.name, "circuit_open"))
                continue

            prompt = p.prompt_adapter(system_prompt) if p.prompt_adapter else system_prompt
            try:
                text = await asyncio.wait_for(p.client.complete(prompt), timeout=p.timeout)
            except asyncio.CancelledError:
                p.breaker.release_probe()
                raise
            except Exception as exc:  # noqa: BLE001
                errors.append((p.name, f"{type(exc).__name__}: {exc}"))
                if is_transient_error(exc):
                    p.breaker.record_failure()
                else:
                    p.breaker.release_probe()
                logger.warning("LLM provider '%s' lỗi: %s", p.name, exc)
                continue

            if not text or not text.strip():
                # thường do model "thinking" tiêu hết max_output_tokens
                p.breaker.release_probe()
                errors.append((p.name, "empty_response"))
                logger.warning("LLM provider '%s' trả response rỗng", p.name)
                continue

            p.breaker.record_success()
            self.last_provider = p.name
            if idx > 0:
                detail = f"dùng '{p.name}' thay cho provider chính; lý do: " + ", ".join(f"{n}={e}" for n, e in errors)
                record(LEVEL_MODEL, detail, "llm")
            return text

        record(LEVEL_MODEL, "tất cả LLM provider thất bại", "llm")
        raise AllProvidersFailed(errors)

    def health(self) -> list[dict[str, Any]]:
        """Dùng cho endpoint /health của agent."""
        return [p.breaker.snapshot() for p in self.providers]


def _setting(name: str, default: Any = None) -> Any:
    try:
        from app.config.settings import settings  # type: ignore
        value = getattr(settings, name, None)
        if value not in (None, ""):
            return value
    except ImportError:
        pass
    return os.getenv(name, default)


def build_default_fallback_llm(llm_client_cls: type, *, breaker_kwargs: dict[str, Any] | None = None) -> FallbackLLMClient:
    """Dựng chuỗi mặc định từ config.

    Ví dụ (gateway/__init__.py):
        from .llm_client import LLMClient
        self.llm = build_default_fallback_llm(LLMClient)

    Biến cấu hình (settings hoặc env):
        GEMINI_MODEL            model chính (mặc định lấy từ LLMClient)
        FALLBACK_LLM_MODEL      model phụ, mặc định gemini-2.5-flash-lite  (kiểm tra tên model còn hiệu lực)
        OLLAMA_FALLBACK_MODEL   nếu đặt (vd llama3:8b) thì thêm provider local cuối chuỗi
    """
    bk = {"failure_threshold": 5, "window_seconds": 60.0, "recovery_seconds": 900.0, **(breaker_kwargs or {})}

    primary = llm_client_cls()
    providers = [ProviderSpec("gemini-primary", primary, CircuitBreaker("gemini-primary", **bk), timeout=30.0)]

    secondary_model = _setting("FALLBACK_LLM_MODEL", "gemini-2.5-flash-lite")
    providers.append(ProviderSpec(
        "gemini-secondary", llm_client_cls(model=secondary_model),
        CircuitBreaker("gemini-secondary", **bk), timeout=30.0, prompt_adapter=adapt_prompt_for_small_model,
    ))

    ollama_model = _setting("OLLAMA_FALLBACK_MODEL")
    if ollama_model:
        providers.append(ProviderSpec(
            "ollama-local", OllamaClient(ollama_model),
            CircuitBreaker("ollama-local", **{**bk, "recovery_seconds": 120.0}), timeout=90.0,
            prompt_adapter=lambda p: adapt_prompt_for_small_model(p, max_chars=4000),
        ))

    return FallbackLLMClient(providers=providers)
