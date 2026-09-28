"""
fallback/tool_fallback.py
-------------------------
CẤP 2 — Tool & Data Fallback cho vòng ReAct.

Khi RAG tool lỗi hạ tầng (Gateway sập, đứt mạng, timeout...), thay vì ném lỗi làm
agent crash, executor trả về 1 observation "suy giảm" theo thứ tự ưu tiên:

  1. Kết quả gần nhất đã cache cho cùng tool + tham số (gắn cờ _stale + tuổi dữ liệu)
  2. LTM lookup (hook `ltm_lookup`, vd truy vấn pgvector "10 phút trước mất mạng...")
  3. Snapshot operational_context đã đính kèm trong event
  4. Thông báo an toàn: "hãy quyết định dựa trên dữ liệu gần nhất / quy tắc an toàn"

Tạo 1 executor MỖI lần evaluate (mỗi lần có RagClient + RagCallBudget riêng).
Executor cũng tự chèn room_id và lọc tham số do LLM sinh ra theo whitelist.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Awaitable, Callable

from .trace import LEVEL_TOOL, record

logger = logging.getLogger("agent.fallback.tool")

ALLOWED_PARAMS: dict[str, set[str]] = {
    "search_history": {"query", "room_id", "time_range"},
    "get_telemetry": {"room_id", "metric", "window"},
    "get_attendance": {"room_id", "session_id", "class_code"},
    "compare_rooms": {"room_ids", "metric", "window"},
    "get_room_history": {"room_id", "hours"},
    "get_schedule": {"room_id", "date"},
    "get_predictions": {"room_id", "metric", "horizon"},
}
REQUIRES_ROOM_ID = {"get_telemetry", "get_room_history", "get_predictions"}
FILL_ROOM_ID = REQUIRES_ROOM_ID | {"get_attendance", "get_schedule", "search_history"}

LtmLookup = Callable[[str, dict[str, Any]], Awaitable[str | None]]


class LastKnownCache:
    """Cache kết quả RAG thành công gần nhất (in-memory, dùng chung nhiều evaluation)."""

    def __init__(self, max_items: int = 512) -> None:
        self._data: dict[str, tuple[float, Any]] = {}
        self._max = max_items

    @staticmethod
    def make_key(tool: str, params: dict[str, Any]) -> str:
        return tool + ":" + json.dumps(params, sort_keys=True, default=str)

    def set(self, key: str, value: Any) -> None:
        if len(self._data) >= self._max:
            self._data.pop(next(iter(self._data)))
        self._data[key] = (time.time(), value)

    def get(self, key: str, max_age: float) -> tuple[Any, float] | None:
        item = self._data.get(key)
        if not item:
            return None
        age = time.time() - item[0]
        return (item[1], age) if age <= max_age else None


_GLOBAL_CACHE = LastKnownCache()


class ResilientToolExecutor:
    def __init__(
        self,
        rag: Any,                       # RagClient (đã gắn RagCallBudget của evaluation này)
        room_id: str,
        *,
        context_snapshot: dict[str, Any] | None = None,
        ltm_lookup: LtmLookup | None = None,
        cache: LastKnownCache | None = None,
        stale_ttl: float = 1800.0,
    ) -> None:
        self._rag = rag
        self.room_id = room_id
        self._snapshot = context_snapshot
        self._ltm = ltm_lookup
        self._cache = cache or _GLOBAL_CACHE
        self._stale_ttl = stale_ttl

    def _prepare(self, tool_name: str, params: dict[str, Any] | None) -> dict[str, Any]:
        if tool_name not in ALLOWED_PARAMS:
            raise ValueError(f"RAG tool '{tool_name}' không nằm trong danh sách cho phép")
        allowed = ALLOWED_PARAMS[tool_name]
        clean = {k: v for k, v in (params or {}).items() if k in allowed and v is not None}
        if tool_name in FILL_ROOM_ID:
            # LLM có thể quên hoặc bịa room_id: với phòng đang đánh giá luôn dùng room_id của event
            if tool_name in REQUIRES_ROOM_ID or "room_id" in clean:
                clean["room_id"] = self.room_id
        return clean

    async def execute(self, tool_name: str, params: dict[str, Any] | None = None) -> str:
        """Luôn trả về str (observation) — không bao giờ ném lỗi hạ tầng ra vòng ReAct."""
        try:
            clean = self._prepare(tool_name, params)
        except ValueError as exc:
            return f"Lỗi tham số: {exc}"

        key = self._cache.make_key(tool_name, clean)
        try:
            result = await self._rag.call_tool(tool_name, clean)
        except Exception as exc:  # noqa: BLE001
            name = type(exc).__name__
            if name == "RagBudgetExceeded":
                return f"{exc}"
            if isinstance(exc, TypeError):
                return f"Lỗi tham số khi gọi '{tool_name}': {exc}"
            status = getattr(exc, "status_code", None)
            if isinstance(status, int) and 400 <= status < 500 and status not in (408, 429):
                # Backend trả lời rõ ràng (vd 404 không có phòng) => không phải sự cố hạ tầng
                return f"Lỗi từ Gateway khi gọi '{tool_name}' (HTTP {status}): {exc}"
            return await self._degrade(tool_name, clean, key, exc)

        self._cache.set(key, result)
        return json.dumps(result, ensure_ascii=False)

    async def _degrade(self, tool_name: str, params: dict[str, Any], key: str, exc: Exception) -> str:
        why = f"{type(exc).__name__}: {exc}"
        logger.warning("RAG tool '%s' lỗi hạ tầng, dùng fallback dữ liệu: %s", tool_name, why)

        cached = self._cache.get(key, self._stale_ttl)
        if cached:
            data, age = cached
            record(LEVEL_TOOL, f"{tool_name}: dùng cache cũ {age:.0f}s ({why})", "rag")
            return json.dumps({
                "_stale": True,
                "_age_seconds": round(age),
                "_warning": "Không kết nối được dữ liệu thời gian thực; đây là kết quả cũ. Hãy hạ confidence.",
                "data": data,
            }, ensure_ascii=False, default=str)

        if self._ltm:
            try:
                ltm = await self._ltm(tool_name, params)
            except Exception as ltm_exc:  # noqa: BLE001
                logger.warning("LTM lookup lỗi: %s", ltm_exc)
                ltm = None
            if ltm:
                record(LEVEL_TOOL, f"{tool_name}: dùng dữ liệu LTM ({why})", "rag")
                return f"[LTM - dữ liệu lịch sử, không phải thời gian thực]\n{ltm}"

        record(LEVEL_TOOL, f"{tool_name}: không có dữ liệu thay thế ({why})", "rag")
        msg = (
            f"Lỗi: Không thể kết nối cảm biến/backend thời gian thực cho '{tool_name}' ({why}). "
            "Hãy đưa ra quyết định dựa trên dữ liệu gần nhất trong event payload hoặc quy tắc an toàn cơ bản, "
            "hạ confidence, và KHÔNG gọi lại tool này."
        )
        if self._snapshot:
            msg += "\nDữ liệu gần nhất từ event: " + json.dumps(self._snapshot, ensure_ascii=False, default=str)[:1500]
        return msg
