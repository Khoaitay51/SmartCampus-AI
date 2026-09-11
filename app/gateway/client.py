from __future__ import annotations
 
import asyncio
import logging
from typing import Any
 
import httpx

try:
    from app.config.settings import settings
except ImportError:  # pragma: no cover - fallback khi chạy standalone/test
    settings = None
 
logger = logging.getLogger("agent.gateway.client")
 
 
def _cfg(name: str, default: Any) -> Any:
    """Đọc config từ app.config.settings, fallback về default nếu thiếu field."""
    return getattr(settings, name, default) if settings else default

class GatewayError(Exception):
    def __init__(self, message: str, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class GatewayClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None, max_retries: int | None = None) -> None:
        self.base_url = (base_url or _cfg("GATEWAY_BASE_URL", "http://gateway:8000/api")).rstrip("/")
        self.timeout = timeout or _cfg("GATEWAY_TIMEOUT_SECONDS", 10.0)
        self.max_retries = max_retries if max_retries is not None else _cfg("GATEWAY_MAX_RETRIES", 2)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "GatewayClient":
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self
 
    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
 
    def _require_client(self) -> httpx.AsyncClient:
        if self._client is None:
            # Cho phép dùng ngoài context manager (agent nên khởi tạo 1 instance
            # dùng chung suốt vòng đời process thay vì mở connection mỗi lần).
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self._client
 
    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        client = self._require_client()
        last_exc: Exception | None = None
 
        for attempt in range(self.max_retries + 1):
            try:
                resp = await client.request(method, path, **kwargs)
                if resp.status_code >= 400:
                    raise GatewayError(
                        f"Gateway trả lỗi {resp.status_code} cho {method} {path}",
                        status_code=resp.status_code,
                        payload=_safe_json(resp),
                    )
                return _safe_json(resp)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                wait = 0.3 * (2**attempt)
                logger.warning(
                    "Gateway %s %s lỗi (attempt %d/%d): %s",
                    method, path, attempt + 1, self.max_retries + 1, exc,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(wait)
                    continue
                raise GatewayError(
                    f"Không kết nối được Gateway sau {self.max_retries + 1} lần thử: {exc}"
                ) from exc
            except GatewayError:
                raise
 
        raise GatewayError(str(last_exc) if last_exc else "Unknown gateway error")  # noqa: TRY002
 
    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request("GET", path, params=params)
 
    async def post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return await self._request("POST", path, json=json)
 
    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
 
 
def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return {"raw": resp.text}