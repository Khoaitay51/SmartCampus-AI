"""
app/config/clock.py
-------------------
Cung cấp đồng hồ tham chiếu cho hệ thống (Clock Injection - QĐ-7 / Phase B2).
Khi BENCHMARK_MODE=True và BENCHMARK_REFERENCE_TIME được cấu hình (hoặc truyền qua context),
trả về thời điểm tham chiếu T0 chuẩn thay vì thời gian wall-clock thật.
Mặc định khi BENCHMARK_MODE=False: trả về datetime.now(timezone.utc).
"""
from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timezone
import logging
from typing import Optional

from app.config.settings import settings

logger = logging.getLogger("app.config.clock")

# Hỗ trợ truyền reference_time theo từng request / testcase qua ContextVar
_request_reference_time: ContextVar[Optional[datetime]] = ContextVar("request_reference_time", default=None)


def set_request_reference_time(dt: datetime | str | None) -> None:
    """Thiết lập reference_time cho context request hiện tại."""
    if dt is None:
        _request_reference_time.set(None)
        return
    if isinstance(dt, str):
        parsed = datetime.fromisoformat(dt)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        _request_reference_time.set(parsed)
    else:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        _request_reference_time.set(dt)


def get_current_time() -> datetime:
    """Lấy thời gian hiện tại của hệ thống.
    
    Quy tắc ưu tiên:
    1. Nếu context request có reference_time -> dùng nó.
    2. Nếu settings.BENCHMARK_MODE=True và có settings.BENCHMARK_REFERENCE_TIME -> dùng nó.
    3. Mặc định (Production): datetime.now(timezone.utc).
    """
    # 1. Check ContextVar
    ctx_dt = _request_reference_time.get()
    if ctx_dt is not None:
        return ctx_dt

    # 2. Check settings (feature flag)
    if getattr(settings, "BENCHMARK_MODE", False):
        ref_str = getattr(settings, "BENCHMARK_REFERENCE_TIME", None)
        if ref_str:
            try:
                parsed = datetime.fromisoformat(ref_str)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed
            except Exception as e:
                logger.warning("Không parse được BENCHMARK_REFERENCE_TIME '%s': %s", ref_str, e)

    # 3. Mặc định wall-clock
    return datetime.now(timezone.utc)
