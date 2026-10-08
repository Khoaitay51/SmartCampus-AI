"""
app/campus/hitl.py
------------------
Module quản lý trạng thái Human-in-the-Loop (HITL) và thực thi lệnh công cụ (Tool Execution)
từ AI Recommendation sang Edge Gateway và MQTT Actuators.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any
from uuid import UUID

import httpx
from app.config.settings import settings
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)

# Runtime state cho chế độ HITL
# True  = Bắt buộc người vận hành xác nhận (Manual Approval)
# False = Chế độ Tự động (Auto-pilot / Auto-execute khi tin cậy cao)
_HITL_ENABLED: bool = True


def is_hitl_enabled() -> bool:
    """Kiểm tra chế độ HITL hiện tại."""
    global _HITL_ENABLED
    return _HITL_ENABLED


def set_hitl_enabled(enabled: bool) -> bool:
    """Bật/tắt chế độ HITL."""
    global _HITL_ENABLED
    _HITL_ENABLED = bool(enabled)
    logger.info("Chế độ HITL đã được đổi thành: %s", "BẬT (Manual Confirm)" if _HITL_ENABLED else "TẮT (Auto-pilot)")
    return _HITL_ENABLED


def translate_recommendation_to_command(tool_name: str, tool_params: dict[str, Any]) -> tuple[str, str] | None:
    """Ánh xạ tên tool và params từ AI Agent sang command_type và command_value chuẩn của Edge Gateway."""
    tool_lower = (tool_name or "").lower().strip()
    
    if tool_lower in ("set_fan", "fan_control"):
        state = str(tool_params.get("state", "on")).lower()
        val = "on" if state in ("on", "1", "true", "high") else "off"
        return "fan", val

    elif tool_lower in ("set_door", "door_control"):
        state = str(tool_params.get("state", "unlocked")).lower()
        val = "locked" if state in ("locked", "lock", "true") else "unlocked"
        return "door", val

    elif tool_lower in ("set_mode", "mode_control"):
        mode = str(tool_params.get("mode", "saving")).lower()
        return "mode", mode

    elif tool_lower in ("trigger_buzzer", "buzzer_control"):
        pattern = str(tool_params.get("pattern", "short")).lower()
        # Edge chấp nhận on, off, double, long, emergency...
        return "buzzer", pattern if pattern in ("off", "0", "false") else "on"

    elif tool_lower in ("set_led", "led_strip_control"):
        state = str(tool_params.get("state", "solid")).lower()
        val = "off" if state in ("off", "0") else "on"
        return "light", val

    elif tool_lower == "send_alert":
        level = str(tool_params.get("level", "info")).lower()
        if level in ("critical", "emergency"):
            return "buzzer", "on"
        return None

    return None


async def dispatch_tool_execution(
    rec_id: UUID | str,
    room_id: UUID | str | None,
    tool_name: str,
    tool_params: dict[str, Any],
    reason: str = "",
    operator: str = "operator",
    is_auto: bool = False,
) -> dict[str, Any]:
    """Gửi lệnh thực thi sang Edge Gateway API để điều khiển cơ cấu chấp hành vật lý thật."""
    cmd_pair = translate_recommendation_to_command(tool_name, tool_params)
    
    room_id_str = str(room_id) if room_id else ""
    if not room_id_str:
        # Fallback lấy room_id từ tool_params nếu có
        room_id_str = str(tool_params.get("room_id", ""))

    result_summary: dict[str, Any] = {
        "recommendation_id": str(rec_id),
        "tool_name": tool_name,
        "tool_params": tool_params,
        "room_id": room_id_str,
        "operator": operator,
        "is_auto": is_auto,
        "command_executed": False,
        "edge_status": "skipped",
    }

    if not cmd_pair:
        logger.info("Tool %s không cần gửi actuator command xuống phần cứng.", tool_name)
        result_summary["edge_status"] = "no_hardware_action_required"
    elif not room_id_str:
        logger.warning("Không có room_id cho tool %s, bỏ qua gọi Edge Gateway.", tool_name)
        result_summary["edge_status"] = "missing_room_id"
    else:
        command_type, command_value = cmd_pair
        result_summary["command_type"] = command_type
        result_summary["command_value"] = command_value

        # Edge base URL (VD: http://localhost:8000 hoặc cấu hình qua settings)
        base_edge_url = settings.BACKEND_BASE_URL.rstrip("/")
        # Nếu settings.BACKEND_BASE_URL kết thúc bằng /api thì dùng trực tiếp, ngược lại thêm /api
        if not base_edge_url.endswith("/api"):
            execute_url = f"{base_edge_url}/api/commands/room/execute"
        else:
            execute_url = f"{base_edge_url}/commands/room/execute"

        edge_payload = {
            "room_id": room_id_str,
            "command_type": command_type,
            "command_value": command_value,
            "reason": f"AI Recommendation {rec_id} ({'Auto-pilot' if is_auto else 'Approved by ' + operator}): {reason}",
            "source": "ai_agent" if is_auto else "admin_hitl",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                logger.info("Đang gửi lệnh sang Edge Gateway: %s với payload %s", execute_url, edge_payload)
                resp = await client.post(execute_url, json=edge_payload)
                if resp.status_code in (200, 202):
                    result_summary["command_executed"] = True
                    result_summary["edge_status"] = "success"
                    result_summary["edge_response"] = resp.json()
                    logger.info("Edge Gateway đã nhận lệnh thành công: %s", resp.text)
                else:
                    result_summary["edge_status"] = f"http_error_{resp.status_code}"
                    result_summary["edge_response"] = resp.text
                    logger.warning("Edge Gateway trả về lỗi: %s - %s", resp.status_code, resp.text)
        except Exception as exc:
            logger.error("Không thể kết nối sang Edge Gateway (%s): %s", execute_url, exc)
            result_summary["edge_status"] = f"connection_failed: {str(exc)}"

        # Phát trực tiếp lệnh điều khiển actuator sang Mosquitto MQTT
        try:
            from app.websocket.mqtt_bridge import publish_mqtt_message
            import uuid as _uuid
            mqtt_topic = f"smartcampus/v1/command/room/{room_id_str}"
            mqtt_payload = {
                "message_id": str(_uuid.uuid4()),
                "source_timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {
                    "room_id": room_id_str,
                    "command_type": command_type,
                    "command_value": command_value,
                    "reason": edge_payload["reason"],
                    "source": edge_payload["source"],
                },
            }
            await publish_mqtt_message(mqtt_topic, mqtt_payload)
            logger.info("Đã phát lệnh điều khiển actuator trực tiếp tới MQTT %s: %s", mqtt_topic, mqtt_payload)
        except Exception as mq_err:
            logger.warning("Không thể phát MQTT trực tiếp cho actuator: %s", mq_err)

    # Broadcast sự kiện tới toàn bộ client qua WebSocket
    ws_payload = {
        "type": "recommendation_executed",
        **result_summary,
    }
    await ws_manager.broadcast(ws_payload)

    # Nếu tool là send_alert, phát riêng gói tin system_alert để Frontend mở ngay Pop up cảnh báo
    if tool_name.lower().strip() == "send_alert":
        alert_payload = {
            "type": "system_alert",
            "alert": {
                "id": str(rec_id),
                "recommendation_id": str(rec_id),
                "room_id": room_id_str,
                "tool_name": "send_alert",
                "message": tool_params.get("message") or reason or "Cảnh báo an ninh / an toàn từ AI Agent",
                "level": str(tool_params.get("level", "warning")).lower(),
                "reason": reason,
                "operator": operator,
                "is_auto": is_auto,
                "status": "approved" if not is_auto else "auto_approved",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
        await ws_manager.broadcast(alert_payload)

    return result_summary
