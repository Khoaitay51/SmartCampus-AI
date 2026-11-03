"""
app/campus/command_translation.py
---------------------------------
Dịch tool-call của AI Agent sang (command_type, command_value) chuẩn của Edge Gateway.

Tách khỏi ``hitl.py`` để là hàm thuần (không phụ thuộc httpx/WebSocket/DB), nhờ vậy
``binding.py`` hash đúng *lệnh thực sự sẽ thực thi* và có thể unit-test độc lập.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def translate_recommendation_to_command(tool_name: str, tool_params: dict[str, Any]) -> tuple[str, str] | None:
    """Ánh xạ tên tool và params từ AI Agent sang command_type và command_value chuẩn của Edge Gateway."""
    tool_lower = (tool_name or "").lower().strip()
    
    if tool_lower in ("set_fan", "fan_control"):
        raw_val = str(tool_params.get("state") or tool_params.get("value") or tool_params.get("status") or "").lower().strip()
        val = "off" if raw_val in ("off", "0", "false", "low", "stop", "tat", "tắt") else "on"
        return "fan", val

    elif tool_lower in ("set_door", "door_control"):
        raw_val = str(tool_params.get("state") or tool_params.get("value") or tool_params.get("status") or "").lower().strip()
        # Fail-Secure: Bắt buộc nhận diện rõ ràng trạng thái; không default sang unlocked!
        if raw_val in ("locked", "lock", "true", "1", "dong", "đóng", "khoa", "khóa", "close", "closed"):
            return "door", "locked"
        elif raw_val in ("unlocked", "unlock", "false", "0", "mo", "mở", "open", "opened"):
            return "door", "unlocked"
        else:
            logger.warning("Fail-Secure: Không nhận diện được giá trị cửa an toàn từ '%s', từ chối dịch lệnh.", raw_val)
            return None

    elif tool_lower in ("set_mode", "mode_control"):
        mode = str(tool_params.get("mode") or tool_params.get("value") or "saving").lower().strip()
        return "mode", mode

    elif tool_lower in ("trigger_buzzer", "buzzer_control"):
        pattern = str(tool_params.get("pattern") or tool_params.get("state") or tool_params.get("value") or "short").lower().strip()
        return "buzzer", pattern if pattern in ("off", "0", "false") else "on"

    elif tool_lower in ("set_led", "led_strip_control"):
        state = str(tool_params.get("state") or tool_params.get("value") or "solid").lower().strip()
        val = "off" if state in ("off", "0") else "on"
        return "light", val

    elif tool_lower == "send_alert":
        level = str(tool_params.get("level", "info")).lower().strip()
        if level in ("critical", "emergency"):
            return "buzzer", "on"
        return None

    return None
