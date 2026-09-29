"""
app/gateway/actuator.py
------------------------
Client gửi lệnh điều khiển thiết bị (Actuation) tới Edge Service (SmartCampus-edge).
Endpoint chuẩn trên Edge: POST /api/commands/room/execute
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

try:
    from app.config.settings import settings
except ImportError:
    settings = None

logger = logging.getLogger("app.gateway.actuator")


class ActuatorClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or getattr(settings, "BACKEND_BASE_URL", "http://localhost:8000")

    async def execute_action(
        self,
        room_id: str,
        tool_name: str,
        args: dict[str, Any],
        reason: str = "",
    ) -> bool:
        """Gửi yêu cầu kích hoạt actuator tới SmartCampus-edge Command Router.

        Edge endpoint: POST /api/commands/room/execute
        Payload: {room_id, command_type, command_value, reason, source}
        """
        url = f"{self.base_url}/api/commands/room/execute"

        # Chuẩn hóa command_type và command_value từ tool call args
        command_type = (
            tool_name.replace("set_", "").replace("trigger_", "").lower()
        )
        if command_type == "led":
            command_type = "light"

        # Trích xuất command_value tương ứng
        command_value = (
            args.get("state")
            or args.get("pattern")
            or args.get("mode")
            or args.get("color")
            or "on"
        )

        payload = {
            "room_id": str(room_id),
            "command_type": command_type,
            "command_value": str(command_value),
            "reason": reason or f"AI recommendation execution: {tool_name}",
            "source": "ai_agent",
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                logger.info(
                    "Execute action `%s` (%s=%s) thành công cho room %s",
                    tool_name, command_type, command_value, room_id,
                )
                return True
        except Exception as exc:
            logger.error("Lỗi khi gửi lệnh actuator `%s` tới %s: %s", tool_name, url, exc)
            return False
