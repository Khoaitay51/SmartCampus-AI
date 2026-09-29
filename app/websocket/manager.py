"""
app/websocket/manager.py
------------------------
WebSocket ConnectionManager — quản lý connections, broadcast messages.
FR-DT-07: WebSocket connection persistent giữa DTwin và FastAPI.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Quản lý tất cả WebSocket connections.

    Hỗ trợ:
    - Track connections theo user_id/role
    - Broadcast message tới tất cả clients
    - Send message tới specific user
    - Room-based subscriptions
    """

    def __init__(self):
        # {websocket: {"user_id": str, "role": str, "rooms": set[str]}}
        self._connections: dict[WebSocket, dict[str, Any]] = {}

    @property
    def active_count(self) -> int:
        return len(self._connections)

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str | None = None,
        role: str | None = None,
    ) -> None:
        """Accept và lưu WebSocket connection."""
        await websocket.accept()
        self._connections[websocket] = {
            "user_id": user_id,
            "role": role,
            "rooms": set(),
        }
        logger.info(
            "WebSocket connected: user=%s role=%s (total=%d)",
            user_id, role, self.active_count,
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove WebSocket connection."""
        info = self._connections.pop(websocket, {})
        logger.info(
            "WebSocket disconnected: user=%s (total=%d)",
            info.get("user_id"), self.active_count,
        )

    def subscribe_room(self, websocket: WebSocket, room_id: str) -> None:
        """Subscribe client tới room updates."""
        if websocket in self._connections:
            self._connections[websocket]["rooms"].add(room_id)

    def unsubscribe_room(self, websocket: WebSocket, room_id: str) -> None:
        """Unsubscribe client khỏi room updates."""
        if websocket in self._connections:
            self._connections[websocket]["rooms"].discard(room_id)

    async def send_personal(self, websocket: WebSocket, data: dict[str, Any]) -> None:
        """Gửi message tới 1 client cụ thể."""
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.warning("Failed to send to client: %s", e)
            self.disconnect(websocket)

    async def broadcast(self, data: dict[str, Any]) -> None:
        """Broadcast message tới TẤT CẢ clients."""
        disconnected = []
        for ws in list(self._connections.keys()):
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)

    async def broadcast_to_room(self, room_id: str, data: dict[str, Any]) -> None:
        """Broadcast message chỉ tới clients đang subscribe room_id."""
        disconnected = []
        for ws, info in list(self._connections.items()):
            if room_id in info.get("rooms", set()):
                try:
                    await ws.send_json(data)
                except Exception:
                    disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)

    async def send_to_role(self, role: str, data: dict[str, Any]) -> None:
        """Gửi message tới tất cả clients có role cụ thể."""
        disconnected = []
        for ws, info in list(self._connections.items()):
            if info.get("role") == role:
                try:
                    await ws.send_json(data)
                except Exception:
                    disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)

    async def send_to_admins(self, data: dict[str, Any]) -> None:
        """Gửi message tới tất cả admin clients."""
        await self.send_to_role("admin", data)


# Singleton instance — import từ bất kỳ đâu
ws_manager = ConnectionManager()
