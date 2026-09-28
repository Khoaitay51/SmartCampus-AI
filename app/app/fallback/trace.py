"""
fallback/trace.py
-----------------
Ghi lại MỌI lần hệ thống phải "hạ cấp" trong 1 lần evaluate để đánh dấu
`is_fallback` (audit / LTM agent_experience_logs).

Dùng ContextVar nên an toàn khi nhiều /evaluate chạy đồng thời (mỗi asyncio task
có trace riêng), và các module con (LLM, tool, parsing) không cần truyền trace
qua tham số:

    with fallback_trace() as trace:
        ... chạy agent ...
    if trace.is_fallback:
        ...  # gắn cờ vào audit log
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Iterator

LEVEL_MODEL = "model"      # Cấp 1: đổi LLM
LEVEL_TOOL = "tool"        # Cấp 2: RAG tool / dữ liệu
LEVEL_PARSING = "parsing"  # Cấp 3: sửa / cạo JSON
LEVEL_RULES = "rules"      # Cấp 4: quy tắc cứng


@dataclass
class FallbackEvent:
    level: str
    detail: str
    component: str = ""
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"level": self.level, "component": self.component, "detail": self.detail, "ts": self.ts}


@dataclass
class FallbackTrace:
    events: list[FallbackEvent] = field(default_factory=list)

    def add(self, level: str, detail: str, component: str = "") -> None:
        self.events.append(FallbackEvent(level, detail, component))

    @property
    def is_fallback(self) -> bool:
        return bool(self.events)

    def __bool__(self) -> bool:
        return self.is_fallback

    @property
    def levels(self) -> list[str]:
        return sorted({e.level for e in self.events})

    def to_dict(self) -> dict[str, Any]:
        return {"is_fallback": self.is_fallback, "levels": self.levels, "events": [e.to_dict() for e in self.events]}

    def to_log_entries(self) -> list[dict[str, Any]]:
        """Trả danh sách audit entries dành cho `fallback_audit_log` của AgentResponse.

        KHÔNG nhét vào `tool_calls_log` — đây là metadata hạ cấp, không phải
        tool call thực tế. Key ``_type: "fallback_audit"`` giúp consumer phân biệt.
        """
        return [
            {"_type": "fallback_audit", "tool": "fallback", **e.to_dict()}
            for e in self.events
        ]

    def summary(self) -> dict[str, Any]:
        """Dict gọn để nhúc vào analysis hoặc structured log.

        Ví dụ: ``{"fallback": True, "levels": ["parsing", "rules"], "event_count": 2}``
        """
        return {
            "fallback": self.is_fallback,
            "levels": self.levels,
            "event_count": len(self.events),
        }


_current: ContextVar[FallbackTrace | None] = ContextVar("fallback_trace", default=None)


@contextmanager
def fallback_trace() -> Iterator[FallbackTrace]:
    trace = FallbackTrace()
    token = _current.set(trace)
    try:
        yield trace
    finally:
        _current.reset(token)


def record(level: str, detail: str, component: str = "") -> None:
    """Ghi 1 sự kiện fallback vào trace hiện tại (no-op nếu không nằm trong fallback_trace())."""
    trace = _current.get()
    if trace is not None:
        trace.add(level, detail, component)
