"""
fallback/circuit_breaker.py
---------------------------
Circuit Breaker 3 trạng thái (mục 3 trong tài liệu nghiên cứu):

  CLOSED    -> request đi bình thường
  OPEN      -> >= failure_threshold lỗi trong window_seconds => chặn ngay, không gọi thử
  HALF_OPEN -> sau recovery_seconds cho ĐÚNG 1 request dò đường;
               thành công => CLOSED, thất bại => OPEN thêm recovery_seconds

Không có `await` bên trong nên an toàn với asyncio đơn luồng (không cần lock).
"""
from __future__ import annotations

import logging
import time
from collections import deque
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger("agent.fallback.breaker")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        window_seconds: float = 60.0,
        recovery_seconds: float = 900.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.recovery_seconds = recovery_seconds
        self._clock = clock
        self._failures: deque[float] = deque()
        self._state = CircuitState.CLOSED
        self._opened_at = 0.0
        self._probe_in_flight = False

    @property
    def state(self) -> CircuitState:
        if self._state is CircuitState.OPEN and self._clock() - self._opened_at >= self.recovery_seconds:
            self._state = CircuitState.HALF_OPEN
            self._probe_in_flight = False
            logger.info("Breaker '%s': OPEN -> HALF_OPEN (cho phép 1 request dò)", self.name)
        return self._state

    def allow_request(self) -> bool:
        state = self.state
        if state is CircuitState.CLOSED:
            return True
        if state is CircuitState.OPEN:
            return False
        # HALF_OPEN: chỉ 1 request dò tại 1 thời điểm
        if self._probe_in_flight:
            return False
        self._probe_in_flight = True
        return True

    def record_success(self) -> None:
        if self.state is CircuitState.OPEN:
            return  # request cũ hoàn thành muộn sau khi đã ngắt, bỏ qua
        if self._state is CircuitState.HALF_OPEN:
            logger.info("Breaker '%s': dò thành công, HALF_OPEN -> CLOSED", self.name)
        self._failures.clear()
        self._state = CircuitState.CLOSED
        self._probe_in_flight = False

    def record_failure(self) -> None:
        state = self.state
        now = self._clock()
        if state is CircuitState.OPEN:
            return
        if state is CircuitState.HALF_OPEN:
            self._trip(now, "request dò thất bại")
            return
        self._failures.append(now)
        while self._failures and now - self._failures[0] > self.window_seconds:
            self._failures.popleft()
        if len(self._failures) >= self.failure_threshold:
            self._trip(now, f"{len(self._failures)} lỗi trong {self.window_seconds:.0f}s")

    def release_probe(self) -> None:
        """Gọi khi request dò kết thúc mà KHÔNG phải lỗi hạ tầng (lỗi 400, response rỗng, bị cancel)."""
        self._probe_in_flight = False

    def _trip(self, now: float, why: str) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = now
        self._probe_in_flight = False
        self._failures.clear()
        logger.error("Breaker '%s' NGẮT MẠCH (%s). Tạm dừng %.0fs.", self.name, why, self.recovery_seconds)

    def snapshot(self) -> dict[str, Any]:
        state = self.state
        retry_in = max(0.0, self.recovery_seconds - (self._clock() - self._opened_at)) if state is CircuitState.OPEN else 0.0
        return {"name": self.name, "state": state.value, "recent_failures": len(self._failures), "retry_in_seconds": round(retry_in, 1)}
