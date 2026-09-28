"""
app/gateway/actuator.py
------------------------
Client gửi lệnh điều khiển thiết bị (Actuation) tới Edge Service hoặc MQTT Gateway.
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

    async def execute_action(self, room_id: str, tool_name: str, args: dict[str, Any]) -> bool:
        """Gửi yêu cầu kích hoạt actuator tới Edge API."""
        url = f"{self.base_url}/api/v1/actuators/execute"
        payload = {
            "room_id": room_id,
            "action": tool_name,
            "parameters": args,
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                logger.info("Execute action `%s` thành công cho room %s", tool_name, room_id)
                return True
        except Exception as exc:
            logger.error("Lỗi khi gửi lệnh actuator `%s`: %s", tool_name, exc)
            return False
