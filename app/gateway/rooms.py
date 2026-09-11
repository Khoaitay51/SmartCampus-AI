"""
gateway/rooms.py
-----------------
Wrapper cho các "Query endpoints" (section 5, đọc data) — dùng khi agent cần
refresh/bổ sung operational_context ngoài dữ liệu gateway đã đính kèm sẵn trong /evaluate.
"""
from __future__ import annotations

from typing import Any, Literal

from .client import GatewayClient

Window = Literal["15m", "1h", "6h", "24h"]


class RoomsClient:
    def __init__(self, client: GatewayClient) -> None:
        self._client = client

    async def list_rooms(self) -> list[dict[str, Any]]:
        """GET /api/rooms — danh sách rooms kèm current state."""
        data = await self._client.get("/rooms")
        return data.get("rooms", data) if isinstance(data, dict) else data

    async def get_room(self, room_id: str) -> dict[str, Any]:
        """GET /api/rooms/{room_id} — room detail + latest telemetry + active session."""
        return await self._client.get(f"/rooms/{room_id}")

    async def get_telemetry(self, room_id: str, window: Window = "15m") -> dict[str, Any]:
        """GET /api/rooms/{room_id}/telemetry?window=... — telemetry array."""
        return await self._client.get(f"/rooms/{room_id}/telemetry", params={"window": window})

    async def get_active_session(self, room_id: str) -> dict[str, Any] | None:
        """GET /api/rooms/{room_id}/sessions?active=true.

        Trả None nếu không có session đang chạy — khớp với `active_session: null`
        trong operational_context (section 1.2).
        """
        data = await self._client.get(f"/rooms/{room_id}/sessions", params={"active": "true"})
        return data or None

    async def get_history(self, room_id: str, hours: int = 24) -> list[dict[str, Any]]:
        """GET /api/rooms/{room_id}/history?hours=... — state change history."""
        data = await self._client.get(f"/rooms/{room_id}/history", params={"hours": hours})
        return data.get("transitions", data) if isinstance(data, dict) else data