"""
gateway/db.py
---------------
Local persistence layer cho AI Agent, dùng SQLite (aiosqlite).

Theo contract, agent KHÔNG kết nối trực tiếp TimescaleDB của Gateway.
DB này là state RIÊNG của agent, tồn tại độc lập với backend, dùng cho:
- Rate limit: max 1 recommendation / room / 30s (section 7, rule 6)
- Auto-execute cooldown: 60s giữa 2 lần execute cùng tool + cùng room (section 3c)
- Daily execution cap: max 50 executions / room / ngày (section 3c)
- Audit trail cục bộ (bổ sung, KHÔNG thay thế /api/ai/audit-log của gateway)

safety/rate_limit.py và safety/confidence.py nên đọc/ghi state qua module này,
thay vì tự giữ state in-memory (sẽ mất khi agent process restart).
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator
try:
    import aiosqlite
except ImportError:
    aiosqlite = None

try:
    from app.config.settings import settings
except ImportError:
    settings = None

DB_PATH = getattr(settings, "AGENT_DB_PATH", None) or "agent_state.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS recommendation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reco_room_time ON recommendation_log(room_id, created_at);

CREATE TABLE IF NOT EXISTS execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    mode TEXT NOT NULL,
    executed_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_exec_room_tool_time ON execution_log(room_id, tool_name, executed_at);
"""


class AgentStateDB:
    """Wrapper quản lý SQLite state, dùng chung cho toàn bộ agent process."""

    def __init__(self, path: str | Path = DB_PATH) -> None:
        self.path = str(path)

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(_SCHEMA)
            await db.commit()

    # ---------- Rate limit: max 1 recommendation / room / 30s (rule 6) ----------

    async def can_recommend(self, room_id: str, window_seconds: float = 30.0) -> bool:
        cutoff = time.time() - window_seconds
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT COUNT(*) FROM recommendation_log WHERE room_id = ? AND created_at >= ?",
                (room_id, cutoff),
            )
            (count,) = await cur.fetchone()
            return count == 0

    async def record_recommendation(self, room_id: str, tool_name: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO recommendation_log (room_id, tool_name, created_at) VALUES (?, ?, ?)",
                (room_id, tool_name, time.time()),
            )
            await db.commit()

    # ---------- Auto-execute cooldown: 60s giữa 2 lần execute cùng tool + room ----------

    async def can_execute(self, room_id: str, tool_name: str, cooldown_seconds: float = 60.0) -> bool:
        cutoff = time.time() - cooldown_seconds
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """SELECT COUNT(*) FROM execution_log
                   WHERE room_id = ? AND tool_name = ? AND executed_at >= ?""",
                (room_id, tool_name, cutoff),
            )
            (count,) = await cur.fetchone()
            return count == 0

    # ---------- Daily cap: max 50 executions / room / ngày ----------

    async def executions_today(self, room_id: str) -> int:
        midnight = _midnight_epoch()
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT COUNT(*) FROM execution_log WHERE room_id = ? AND executed_at >= ?",
                (room_id, midnight),
            )
            (count,) = await cur.fetchone()
            return count

    async def under_daily_cap(self, room_id: str, cap: int = 50) -> bool:
        return await self.executions_today(room_id) < cap

    async def record_execution(self, room_id: str, tool_name: str, mode: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO execution_log (room_id, tool_name, mode, executed_at) VALUES (?, ?, ?, ?)",
                (room_id, tool_name, mode, time.time()),
            )
            await db.commit()


def _midnight_epoch() -> float:
    now = time.localtime()
    midnight = time.struct_time((now.tm_year, now.tm_mon, now.tm_mday, 0, 0, 0, 0, 0, now.tm_isdst))
    return time.mktime(midnight)


_db_instance: AgentStateDB | None = None


@asynccontextmanager
async def get_db() -> AsyncIterator[AgentStateDB]:
    """Dependency-style accessor, dùng trong api/evaluate.py hoặc safety/*.py.

        async with get_db() as db:
            if not await db.can_recommend(room_id):
                ...
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = AgentStateDB()
        await _db_instance.init()
    yield _db_instance