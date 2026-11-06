"""
app/gateway/actuator.py
------------------------
<<<<<<< HEAD
Client gửi lệnh điều khiển thiết bị (Actuation) tới Edge Service hoặc MQTT Gateway.
=======
Client gửi lệnh điều khiển thiết bị (Actuation) tới Edge Service (SmartCampus-edge).
Endpoint chuẩn trên Edge: POST /api/commands/room/execute
>>>>>>> a3058cae6ead4c2ccd28a68bb998893ba9123a5c
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

<<<<<<< HEAD
    async def execute_action(self, room_id: str, tool_name: str, args: dict[str, Any]) -> bool:
        """Gửi yêu cầu kích hoạt actuator tới Edge API."""
        url = f"{self.base_url}/api/v1/actuators/execute"
        payload = {
            "room_id": room_id,
            "action": tool_name,
            "parameters": args,
        }
=======
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
        b_url = self.base_url.rstrip("/")
        url = f"{b_url}/commands/room/execute" if b_url.endswith("/api") else f"{b_url}/api/commands/room/execute"

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

>>>>>>> a3058cae6ead4c2ccd28a68bb998893ba9123a5c
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
<<<<<<< HEAD
                logger.info("Execute action `%s` thành công cho room %s", tool_name, room_id)
                return True
        except Exception as exc:
            logger.error("Lỗi khi gửi lệnh actuator `%s`: %s", tool_name, exc)
=======
                logger.info(
                    "Execute action `%s` (%s=%s) thành công cho room %s",
                    tool_name, command_type, command_value, room_id,
                )
                return True
        except Exception as exc:
            logger.error("Lỗi khi gửi lệnh actuator `%s` tới %s: %s", tool_name, url, exc)
>>>>>>> a3058cae6ead4c2ccd28a68bb998893ba9123a5c
            return False
